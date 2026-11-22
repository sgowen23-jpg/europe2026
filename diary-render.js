/* Photo diary renderer, shared by diary.html (the live page) and
   diary-picker.html (its "Preview" button), so both look identical.

   DiaryRender.render(container, data, opts)
     data  = diary.json contents (see diary-picker.html for the shape)
     opts.src(photo) -> URL to show for a photo (defaults to "diary/" + photo.src)
*/
(function () {
  var CSS = [
    '.dy{--ink:#1c1a17;--muted:#7b756c;--accent:#214e75;--paper:#faf7f2;--rule:#e2dbd0;font-family:Inter,system-ui,sans-serif;color:var(--ink);background:var(--paper);}',
    '.dy *{box-sizing:border-box;}',
    /* hero */
    '.dy-hero{position:relative;min-height:88vh;display:flex;align-items:flex-end;color:#fff;background:#2b2a28 center/cover no-repeat;}',
    '.dy-hero::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 40%,rgba(0,0,0,.55));}',
    '.dy-hero-in{position:relative;z-index:1;width:100%;max-width:1100px;margin:0 auto;padding:0 20px 9vh;}',
    '.dy-kicker{font-size:.72rem;letter-spacing:.24em;text-transform:uppercase;opacity:.85;margin-bottom:.8rem;}',
    '.dy-hero h1{font-family:"Playfair Display",Georgia,serif;font-style:italic;font-weight:600;font-size:clamp(2.4rem,7vw,5rem);line-height:1;margin:0 0 .7rem;}',
    '.dy-hero p{font-size:1rem;opacity:.9;margin:0;}',
    '.dy-hero.plain{min-height:auto;color:var(--accent);background:none;padding-top:12vh;}',
    '.dy-hero.plain::after{display:none;}',
    '.dy-hero.plain .dy-hero-in{padding-bottom:4vh;text-align:center;}',
    /* intro + chapter nav */
    '.dy-intro{max-width:620px;margin:0 auto;padding:4rem 20px 1rem;font-size:1.08rem;line-height:1.85;text-align:center;}',
    '.dy-nav{position:sticky;top:0;z-index:20;background:rgba(250,247,242,.94);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);border-bottom:1px solid var(--rule);}',
    '.dy-nav-in{display:flex;gap:.3rem;overflow-x:auto;padding:.55rem 16px;max-width:1100px;margin:0 auto;scrollbar-width:none;}',
    '.dy-nav-in::-webkit-scrollbar{display:none;}',
    '.dy-nav a{flex-shrink:0;font-size:.74rem;font-weight:600;letter-spacing:.04em;color:var(--accent);text-decoration:none;padding:.32rem .75rem;border-radius:20px;border:1px solid transparent;}',
    '.dy-nav a:hover,.dy-nav a.on{border-color:var(--accent);}',
    '.dy-nav .dy-home{opacity:.7;}',
    /* chapters */
    '.dy-ch{padding:5rem 0 1rem;scroll-margin-top:44px;}',
    '.dy-ch-hd{text-align:center;max-width:680px;margin:0 auto 3rem;padding:0 20px;}',
    '.dy-ch-num{font-size:.7rem;letter-spacing:.28em;text-transform:uppercase;color:var(--muted);}',
    '.dy-ch-hd h2{font-family:"Playfair Display",Georgia,serif;font-weight:700;font-size:clamp(2.2rem,6vw,3.6rem);color:var(--accent);margin:.5rem 0 .3rem;line-height:1.05;}',
    '.dy-ch-dates{font-size:.85rem;color:var(--muted);}',
    '.dy-ch-hd .dy-text{margin-top:1.6rem;}',
    /* days */
    '.dy-day{margin:0 auto 4rem;}',
    '.dy-day-hd{max-width:620px;margin:0 auto 1.6rem;padding:0 20px;}',
    '.dy-date{font-size:.7rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);display:flex;align-items:center;gap:.8rem;}',
    '.dy-date::after{content:"";flex:1;height:1px;background:var(--rule);}',
    '.dy-day-hd h3{font-family:"Playfair Display",Georgia,serif;font-style:italic;font-weight:600;font-size:1.6rem;margin:.7rem 0 0;line-height:1.2;}',
    '.dy-text{font-size:1.02rem;line-height:1.85;margin-top:1rem;}',
    '.dy-text p{margin:0 0 1em;}',
    /* photos */
    '.dy-row{max-width:1100px;margin:0 auto 14px;padding:0 20px;display:flex;gap:14px;}',
    '.dy-row figure{margin:0;flex:1;min-width:0;}',
    '.dy-row.full{max-width:1100px;}',
    '.dy-row.single{max-width:640px;}',
    '.dy-row.pair figure{flex:var(--r,1);}',
    '.dy-row img{display:block;width:100%;height:auto;background:#ebe5db;cursor:zoom-in;}',
    '.dy-row figcaption{font-size:.8rem;font-style:italic;color:var(--muted);margin-top:.5rem;line-height:1.5;}',
    '@media(max-width:600px){.dy-row{padding:0;gap:4px;margin-bottom:4px;}.dy-row figcaption{padding:0 16px;}.dy-ch{padding-top:3.5rem;}}',
    /* footer */
    '.dy-end{text-align:center;padding:4rem 20px 5rem;color:var(--muted);font-size:.85rem;}',
    '.dy-end a{color:var(--accent);}',
    '.dy-empty{max-width:520px;margin:0 auto;padding:3rem 20px 6rem;text-align:center;line-height:1.8;color:var(--muted);}',
    /* lightbox */
    '.dy-lb{position:fixed;inset:0;z-index:1000;background:rgba(12,12,12,.96);display:none;align-items:center;justify-content:center;flex-direction:column;}',
    '.dy-lb.on{display:flex;}',
    '.dy-lb img{max-width:96vw;max-height:86vh;object-fit:contain;}',
    '.dy-lb-cap{color:#ddd;font-size:.85rem;font-style:italic;margin-top:.8rem;padding:0 20px;text-align:center;min-height:1.2em;}',
    '.dy-lb button{position:absolute;background:none;border:0;color:#fff;font-size:2rem;cursor:pointer;padding:1rem;opacity:.75;}',
    '.dy-lb button:hover{opacity:1;}',
    '.dy-lb .x{top:0;right:0;}.dy-lb .p{left:0;top:50%;transform:translateY(-50%);}.dy-lb .n{right:0;top:50%;transform:translateY(-50%);}'
  ].join('\n');

  var MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  var DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function prettyDate(iso) {
    var p = (iso || '').split('-');
    if (p.length !== 3) return iso || '';
    var d = new Date(+p[0], +p[1] - 1, +p[2]);
    return DAYS[d.getDay()] + ', ' + d.getDate() + ' ' + MONTHS[d.getMonth()];
  }
  function paragraphs(text) {
    var box = el('div', 'dy-text');
    String(text).split(/\n\s*\n/).forEach(function (para) {
      if (!para.trim()) return;
      var p = el('p');
      para.split('\n').forEach(function (line, i) {
        if (i) p.appendChild(document.createElement('br'));
        p.appendChild(document.createTextNode(line));
      });
      box.appendChild(p);
    });
    return box;
  }
  function slug(s, i) {
    return 'ch-' + (i + 1) + '-' + String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  }
  function isPortrait(ph) { return ph.h > ph.w * 1.05; }

  /* Group a day's photos into rows: wide/landscape photos get a full row,
     two portraits in a row sit side by side, a lone portrait is centred. */
  function rows(photos) {
    var out = [], i = 0;
    while (i < photos.length) {
      var a = photos[i], b = photos[i + 1];
      if (!a.wide && isPortrait(a) && b && !b.wide && isPortrait(b)) { out.push({ kind: 'pair', items: [a, b] }); i += 2; }
      else if (!a.wide && isPortrait(a)) { out.push({ kind: 'single', items: [a] }); i += 1; }
      else { out.push({ kind: 'full', items: [a] }); i += 1; }
    }
    return out;
  }

  function injectCss() {
    if (document.getElementById('dy-css')) return;
    var s = el('style'); s.id = 'dy-css'; s.textContent = CSS;
    document.head.appendChild(s);
  }

  function render(container, data, opts) {
    opts = opts || {};
    var src = opts.src || function (ph) { return 'diary/' + ph.src; };
    injectCss();
    container.innerHTML = '';
    var root = el('div', 'dy');
    container.appendChild(root);
    var all = []; // flat list for the lightbox

    // Hero
    var hero = el('header', 'dy-hero');
    var coverPh = data.cover && findPhoto(data, data.cover);
    if (coverPh) hero.style.backgroundImage = 'url("' + src(coverPh) + '")';
    else hero.className += ' plain';
    var hin = el('div', 'dy-hero-in');
    if (data.kicker) hin.appendChild(el('div', 'dy-kicker', data.kicker));
    hin.appendChild(el('h1', null, data.title || 'A Photo Diary'));
    if (data.subtitle) hin.appendChild(el('p', null, data.subtitle));
    hero.appendChild(hin);
    root.appendChild(hero);

    var chapters = (data.chapters || []).filter(function (c) {
      return (c.days || []).some(function (d) { return (d.photos || []).length || (d.text || '').trim(); }) || (c.intro || '').trim();
    });

    // Chapter nav
    var nav = el('nav', 'dy-nav'), navIn = el('div', 'dy-nav-in');
    if (opts.homeHref) { var h = el('a', 'dy-home', '← Trip'); h.href = opts.homeHref; navIn.appendChild(h); }
    chapters.forEach(function (c, i) {
      var a = el('a', null, c.place || 'Chapter ' + (i + 1));
      a.href = '#' + slug(c.place, i);
      a.onclick = function (e) {
        e.preventDefault();
        var t = root.querySelector('#' + slug(c.place, i));
        if (t) t.scrollIntoView({ behavior: 'smooth' });
      };
      navIn.appendChild(a);
    });
    nav.appendChild(navIn);
    root.appendChild(nav);

    if ((data.intro || '').trim()) {
      var intro = el('div', 'dy-intro');
      intro.appendChild(paragraphs(data.intro));
      root.appendChild(intro);
    }

    if (!chapters.length) {
      root.appendChild(el('div', 'dy-empty', opts.emptyText || 'Photos coming soon.'));
    }

    chapters.forEach(function (c, ci) {
      var sec = el('section', 'dy-ch');
      sec.id = slug(c.place, ci);
      var hd = el('div', 'dy-ch-hd');
      hd.appendChild(el('div', 'dy-ch-num', 'Chapter ' + (ci + 1) + (c.country ? ' · ' + c.country : '')));
      hd.appendChild(el('h2', null, c.place || ''));
      if (c.dates) hd.appendChild(el('div', 'dy-ch-dates', c.dates));
      if ((c.intro || '').trim()) hd.appendChild(paragraphs(c.intro));
      sec.appendChild(hd);

      (c.days || []).forEach(function (d) {
        var photos = d.photos || [];
        if (!photos.length && !(d.text || '').trim() && !(d.title || '').trim()) return;
        var day = el('article', 'dy-day');
        var dh = el('div', 'dy-day-hd');
        dh.appendChild(el('div', 'dy-date', prettyDate(d.date)));
        if ((d.title || '').trim()) dh.appendChild(el('h3', null, d.title));
        if ((d.text || '').trim()) dh.appendChild(paragraphs(d.text));
        day.appendChild(dh);

        rows(photos).forEach(function (r) {
          var row = el('div', 'dy-row ' + r.kind);
          r.items.forEach(function (ph) {
            var fig = el('figure');
            if (r.kind === 'pair') fig.style.setProperty('--r', (ph.w / ph.h).toFixed(3));
            var img = el('img');
            img.loading = 'lazy';
            img.decoding = 'async';
            img.src = src(ph);
            if (ph.w && ph.h) { img.width = ph.w; img.height = ph.h; }
            img.alt = ph.caption || ((c.place || '') + ', ' + prettyDate(d.date));
            var idx = all.length;
            all.push(ph);
            img.onclick = function () { openLb(idx); };
            fig.appendChild(img);
            if ((ph.caption || '').trim()) fig.appendChild(el('figcaption', null, ph.caption));
            row.appendChild(fig);
          });
          day.appendChild(row);
        });
        sec.appendChild(day);
      });
      root.appendChild(sec);
    });

    var end = el('footer', 'dy-end');
    end.appendChild(el('div', null, data.signoff || 'The end. Thanks for coming along.'));
    if (opts.homeHref) {
      end.appendChild(document.createElement('br'));
      var back = el('a', null, '← Back to the trip'); back.href = opts.homeHref;
      end.appendChild(back);
    }
    root.appendChild(end);

    // Highlight the chapter currently on screen in the nav
    if ('IntersectionObserver' in window && chapters.length) {
      var links = navIn.querySelectorAll('a:not(.dy-home)');
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          var i = Array.prototype.indexOf.call(root.querySelectorAll('.dy-ch'), en.target);
          links.forEach(function (l, j) { l.classList.toggle('on', j === i); });
          if (links[i] && links[i].scrollIntoView && navIn.scrollWidth > navIn.clientWidth) {
            navIn.scrollTo({ left: links[i].offsetLeft - 40, behavior: 'smooth' });
          }
        });
      }, { rootMargin: '-45% 0px -50% 0px' });
      root.querySelectorAll('.dy-ch').forEach(function (s) { io.observe(s); });
    }

    // Lightbox
    var lb = el('div', 'dy-lb'), lbImg = el('img'), lbCap = el('div', 'dy-lb-cap');
    var bx = el('button', 'x', '×'), bp = el('button', 'p', '‹'), bn = el('button', 'n', '›');
    bx.setAttribute('aria-label', 'Close'); bp.setAttribute('aria-label', 'Previous'); bn.setAttribute('aria-label', 'Next');
    lb.appendChild(lbImg); lb.appendChild(lbCap); lb.appendChild(bx); lb.appendChild(bp); lb.appendChild(bn);
    root.appendChild(lb);
    var cur = 0;
    function show(i) {
      cur = (i + all.length) % all.length;
      lbImg.src = src(all[cur]);
      lbCap.textContent = all[cur].caption || '';
    }
    function openLb(i) { show(i); lb.classList.add('on'); }
    function closeLb() { lb.classList.remove('on'); }
    bx.onclick = closeLb;
    bp.onclick = function (e) { e.stopPropagation(); show(cur - 1); };
    bn.onclick = function (e) { e.stopPropagation(); show(cur + 1); };
    lb.onclick = function (e) { if (e.target === lb) closeLb(); };
    var sx = null;
    lb.addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; }, { passive: true });
    lb.addEventListener('touchend', function (e) {
      if (sx == null) return;
      var dx = e.changedTouches[0].clientX - sx; sx = null;
      if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1));
    });
    function onKey(e) {
      if (!lb.classList.contains('on')) return;
      if (e.key === 'Escape') closeLb();
      else if (e.key === 'ArrowLeft') show(cur - 1);
      else if (e.key === 'ArrowRight') show(cur + 1);
    }
    if (container._dyKey) document.removeEventListener('keydown', container._dyKey);
    container._dyKey = onKey;
    document.addEventListener('keydown', onKey);
  }

  function findPhoto(data, srcName) {
    var hit = null;
    (data.chapters || []).forEach(function (c) {
      (c.days || []).forEach(function (d) {
        (d.photos || []).forEach(function (p) { if (p.src === srcName) hit = p; });
      });
    });
    return hit;
  }

  window.DiaryRender = { render: render, prettyDate: prettyDate };
})();
