/** Inspect existing TypeScript interfaces without emitting code or generating types. */
import ts from 'typescript'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const filename = resolve(process.argv[2] ?? fileURLToPath(new URL('../src/api/contracts.ts', import.meta.url)))
const program = ts.createProgram([filename], { strict: true, noEmit: true, target: ts.ScriptTarget.ESNext })
const diagnostics = ts.getPreEmitDiagnostics(program)
if (diagnostics.length) {
  throw new Error(ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCurrentDirectory: () => process.cwd(),
    getCanonicalFileName: name => name,
    getNewLine: () => '\n',
  }))
}
const checker = program.getTypeChecker()
const source = program.getSourceFile(filename)
const result = {}
for (const declaration of source.statements) {
  if (!ts.isInterfaceDeclaration(declaration) || declaration.name.text === 'ApiClient') continue
  if (!declaration.modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword)) continue
  const type = checker.getTypeAtLocation(declaration)
  const fields = {}
  for (const property of checker.getPropertiesOfType(type)) {
    const propertyType = checker.getTypeOfSymbolAtLocation(property, declaration)
    const alternatives = propertyType.isUnion() ? propertyType.types : [propertyType]
    fields[property.name] = {
      required: !(property.flags & ts.SymbolFlags.Optional),
      nullable: alternatives.some(part => Boolean(part.flags & ts.TypeFlags.Null)),
    }
  }
  result[declaration.name.text] = fields
}
process.stdout.write(JSON.stringify(result))
