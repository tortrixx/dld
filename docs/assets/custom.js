/* ==========================================================================
   docs/assets/custom.js —— 站点呈现增强
   --------------------------------------------------------------------------
   只做一件事：把「图片 + 斜体图注」包成 <figure>/<figcaption>，
   让 CSS 能给波形图统一加框、加题注，并让图能被键盘打开放大。
   自己写而不是再装一个插件：站点只需要这一个行为，可控、不额外引入依赖。
   ========================================================================== */
(function () {
  'use strict';

  function isWhitespaceText(node) {
    return node.nodeType === 3 && node.textContent.trim() === '';
  }

  function wrapOne(p) {
    // 只处理"整段就是一张图（可能带一句斜体图注）"的段落。
    // 段落里只要还有正文文字，就整段不动 —— 否则 removeChild 会把正文一起删掉。
    var hasText = Array.prototype.some.call(p.childNodes, function (n) {
      return n.nodeType === 3 && !isWhitespaceText(n);
    });
    if (hasText) return;

    var els = Array.prototype.filter.call(p.childNodes, function (n) {
      return n.nodeType === 1;
    });
    if (els.length < 1 || els.length > 2) return;
    if (els[0].tagName !== 'IMG') return;

    var img = els[0];
    var em = null;
    if (els.length === 2) {
      if (els[1].tagName !== 'EM') return;   // 第二个元素不是斜体图注就不动
      em = els[1];
    }

    var fig = document.createElement('figure');
    fig.className = 'doc-figure';
    p.parentNode.insertBefore(fig, p);

    img.removeAttribute('width');
    img.removeAttribute('height');
    fig.appendChild(img);

    var cap = document.createElement('figcaption');
    if (em) {
      // 把 <em> 的子节点整体搬过来，这样图注里的 `行内代码` 等标记不会丢
      while (em.firstChild) cap.appendChild(em.firstChild);
    } else {
      cap.textContent = (img.getAttribute('alt') || '').trim();
    }
    if (cap.textContent.trim()) {
      fig.appendChild(cap);
    }

    // 键盘可达：图片可以被 Tab 聚焦，回车/空格等价于点击放大
    img.setAttribute('tabindex', '0');
    img.setAttribute('role', 'button');
    img.setAttribute('aria-label', '放大查看：' + cap.textContent.trim());
    img.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        img.click();
      }
    });

    p.parentNode.removeChild(p);
  }

  function wrapFigures(root) {
    Array.prototype.forEach.call(root.querySelectorAll('p'), wrapOne);
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
