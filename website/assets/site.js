/* ============================================================
   CodeNova AI — shared site behaviour
   - OS detection (Windows / macOS) + download links
   - Header mobile toggle + reveal-on-scroll
   - TargetCursor init
   ============================================================ */
(function () {
  'use strict';

  // ----- Download config (update these paths when installers change) -----
  // Installers are hosted as GitHub Release assets (files exceed GitHub's
  // 100MB repo limit). Update the tag below when publishing a new version.
  var RELEASE = 'https://github.com/mahadabbasi19/final-fyp/releases/download/v2.0.0/';
  var DOWNLOADS = {
    windows: {
      label: 'Download for Windows',
      url: RELEASE + 'CodeNova-IDE-Setup-2.0.0.exe',
      os: 'Windows'
    },
    mac: {
      label: 'Download for macOS',
      url: RELEASE + 'CodeNova-IDE-2.0.0-macOS.dmg',
      os: 'macOS'
    }
  };

  function detectOS() {
    var ua = (navigator.userAgent || '').toLowerCase();
    var platform = (navigator.platform || '').toLowerCase();
    if (/win/.test(platform) || ua.indexOf('windows') !== -1) return 'windows';
    if (/mac/.test(platform) || ua.indexOf('mac') !== -1 || ua.indexOf('darwin') !== -1) return 'mac';
    return 'windows'; // sensible default for a desktop IDE
  }

  window.CodeNova = {
    downloads: DOWNLOADS,
    detectOS: detectOS,
    currentDownload: function () { return DOWNLOADS[detectOS()]; }
  };

  function triggerDownload(cfg) {
    var a = document.createElement('a');
    a.href = cfg.url;
    a.setAttribute('download', '');
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var current = DOWNLOADS[detectOS()];

    // Auto-detecting download buttons: [data-download="auto"]
    Array.prototype.forEach.call(document.querySelectorAll('[data-download="auto"]'), function (btn) {
      var labelEl = btn.querySelector('[data-download-label]');
      if (labelEl) labelEl.textContent = current.label;
      else if (btn.hasAttribute('data-download-label-self')) btn.textContent = current.label;
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        triggerDownload(current);
      });
    });

    // Explicit-OS download buttons: [data-download="windows"|"mac"]
    Array.prototype.forEach.call(document.querySelectorAll('[data-download="windows"],[data-download="mac"]'), function (btn) {
      var os = btn.getAttribute('data-download');
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        triggerDownload(DOWNLOADS[os]);
      });
    });

    // ----- First-run notes (unsigned builds) -----
    // Every primary download button gets an OS-appropriate note so users
    // aren't surprised by SmartScreen / Gatekeeper.
    var NOTES = {
      windows: 'After downloading, run the installer. If Windows shows “Windows protected your PC”, click More info → Run anyway. This appears because the app is not code-signed, not because anything is wrong.',
      mac: 'After downloading, drag CodeNova to Applications, then right-click → Open → Open on first launch (required once for apps outside the App Store).'
    };
    Array.prototype.forEach.call(document.querySelectorAll('.btn[data-download]'), function (btn) {
      // Skip header buttons (too cramped) and centered CTA buttons marked
      // data-no-note (a paragraph under them breaks the layout).
      if (btn.closest('.site-header') || btn.hasAttribute('data-no-note')) return;
      var os = btn.getAttribute('data-download');
      if (os === 'auto') os = detectOS();
      var note = document.createElement('p');
      note.className = 'dl-note';
      note.textContent = NOTES[os] || NOTES.windows;
      btn.insertAdjacentElement('afterend', note);
    });

    // Mobile nav toggle
    var toggle = document.querySelector('.nav-toggle');
    var nav = document.querySelector('.nav');
    if (toggle && nav) {
      toggle.addEventListener('click', function () { nav.classList.toggle('open'); });
    }

    // Reveal on scroll
    var reveals = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12 });
      reveals.forEach(function (el) { io.observe(el); });
    } else {
      reveals.forEach(function (el) { el.classList.add('is-visible'); });
    }

    // Spinning target cursor — active ONLY over the floating feature bars.
    if (typeof window.initTargetCursor === 'function') {
      window.initTargetCursor({
        zoneSelector: '.float-bar',
        targetSelector: '.cursor-target',
        spinDuration: 2,
        hideDefaultCursor: true,
        parallaxOn: true,
        hoverDuration: 0.2,
        cursorColor: '#ffffff',
        cursorColorOnTarget: '#B497CF'
      });
    }
  });
})();
