<template>
  <main class="workspace">
    <header class="masthead">
      <a class="brand" href="#main-content" aria-label="Paper Evidence Agent 首页">
        <span class="brand-mark" aria-hidden="true">P</span>
        <span>Paper Evidence Agent</span>
      </a>
      <span class="status-badge"><span aria-hidden="true"></span>项目骨架</span>
    </header>

    <section id="main-content" class="intro" aria-labelledby="page-title">
      <p class="eyebrow">论文引文证据核验</p>
      <h1 id="page-title">让每条判断<br />都有原文可查。</h1>
      <p class="intro-copy">输入一条论断与被引文献 DOI，复查两者的证据关系。</p>
      <p class="notice" role="status">功能待实现 · 当前页面仅展示项目骨架。</p>
    </section>

    <section class="check-panel" aria-labelledby="check-title">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">新的核验</p>
          <h2 id="check-title">论断与文献</h2>
        </div>
        <span class="pending-label">待接入</span>
      </div>
      <label for="claim">论断原句</label>
      <textarea id="claim" disabled rows="4" placeholder="核验功能开放后，可在这里输入中文或英文论断。"></textarea>
      <label for="doi">被引文献 DOI</label>
      <input id="doi" disabled type="text" placeholder="DOI 来源解析待实现" />
      <div class="panel-footer">
        <p>来源解析、授权与任务执行将在后续实现。</p>
        <button type="button" disabled>功能待实现 <span aria-hidden="true">↗</span></button>
      </div>
    </section>

    <section class="history" aria-labelledby="history-title">
      <div class="history-heading">
        <h2 id="history-title">本地历史</h2>
        <span>待接入</span>
      </div>
      <p>历史记录功能尚未实现。</p>
    </section>
    <footer>单条论断 · 指定文献 · 原文位置</footer>
  </main>
</template>
