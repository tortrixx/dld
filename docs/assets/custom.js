/* ==========================================================================
   docs/assets/custom.js —— 站点呈现增强
   --------------------------------------------------------------------------
   只做一件事：把「图片 + 斜体图注」包成 <figure>/<figcaption>，
   让 CSS 能给波形图统一加框、加题注。
   自己写而不是再装一个插件：站点只需要这一个行为，自己写可控、不额外引入依赖。
   ========================================================================== */
(function () {
  'use strict';

  function wrapFigures(root) {
    var paras = root.querySelectorAll('p');
    Array.prototype.forEach.call(paras, function (p) {
      // 只处理"整段就是一张图（可能带一句斜体图注）"的段落，正文里的行内小图不动
      var els = Array.prototype.filter.call(p.childNodes, function (n) {
        return n.nodeType === 1;
      });
      if (els.length < 1 || els.length > 2) return;
      if (els[0].tagName !== 'IMG') return;

      var img = els[0];
      var caption = null;
      if (els.length === 2) {
        if (els[1].tagName !== 'EM') return;   // 第二个元素不是斜体图注就不动
        caption = els[1].textContent.trim();
      }
      if (!caption) caption = (img.getAttribute('alt') || '').trim();

      var fig = document.createElement('figure');
      fig.className = 'doc-figure';
      p.parentNode.insertBefore(fig, p);

      img.removeAttribute('width');
      img.removeAttribute('height');
      fig.appendChild(img);

      if (caption) {
        var cap = document.createElement('figcaption');
        cap.textContent = caption;
        fig.appendChild(cap);
      }
      p.parentNode.removeChild(p);
    });
  }

  window.$docsify = window.$docsify || {};
  window.$docsify.plugins = (window.$docsify.plugins || []).concat([
    function (hook) {
      hook.doneEach(function () {
        var root = document.querySelector('.markdown-section');
        if (root) wrapFigures(root);
      });
    }
  ]);
})();
