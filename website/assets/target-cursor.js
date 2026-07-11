/*
 * TargetCursor — vanilla JS port of the react-bits <TargetCursor /> component.
 * Requires GSAP to be loaded on the page (window.gsap).
 *
 * Usage:
 *   initTargetCursor({
 *     spinDuration: 2,
 *     hideDefaultCursor: true,
 *     hoverDuration: 0.2,
 *     parallaxOn: true,
 *     cursorColor: '#ffffff',
 *     cursorColorOnTarget: '#B497CF',
 *     targetSelector: '.cursor-target'
 *   });
 */
(function () {
  'use strict';

  function isMobile() {
    if (typeof window === 'undefined') return false;
    const hasTouchScreen = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const isSmallScreen = window.innerWidth <= 768;
    const ua = (navigator.userAgent || navigator.vendor || window.opera || '').toLowerCase();
    const mobileRegex = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i;
    return (hasTouchScreen && isSmallScreen) || mobileRegex.test(ua);
  }

  // A position:fixed element is positioned relative to the viewport UNLESS an
  // ancestor establishes a containing block (transform/perspective/filter/etc).
  function getContainingBlock(element) {
    let node = element && element.parentElement;
    while (node && node !== document.documentElement) {
      const s = getComputedStyle(node);
      if (
        s.transform !== 'none' ||
        s.perspective !== 'none' ||
        s.filter !== 'none' ||
        s.willChange.includes('transform') ||
        s.willChange.includes('perspective') ||
        s.willChange.includes('filter') ||
        /paint|layout|strict|content/.test(s.contain)
      ) {
        return node;
      }
      node = node.parentElement;
    }
    return null;
  }

  function getContainingBlockOffset(block) {
    if (!block) return { x: 0, y: 0 };
    const rect = block.getBoundingClientRect();
    return { x: rect.left + block.clientLeft, y: rect.top + block.clientTop };
  }

  window.initTargetCursor = function initTargetCursor(options) {
    const opts = Object.assign(
      {
        targetSelector: '.cursor-target',
        // When set, the target cursor only appears while the pointer is inside
        // element(s) matching this selector (e.g. the hero mockup). Outside the
        // zone the normal system cursor is shown untouched.
        zoneSelector: null,
        spinDuration: 2,
        hideDefaultCursor: true,
        hoverDuration: 0.2,
        parallaxOn: true,
        cursorColor: '#ffffff',
        cursorColorOnTarget: undefined
      },
      options || {}
    );

    if (isMobile() || !window.gsap) return function () {};
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return function () {};

    const gsap = window.gsap;
    const borderWidth = 3;
    const cornerSize = 12;

    // Build cursor DOM
    const cursor = document.createElement('div');
    cursor.className = 'target-cursor-wrapper';
    const dot = document.createElement('div');
    dot.className = 'target-cursor-dot';
    dot.style.backgroundColor = opts.cursorColor;
    cursor.appendChild(dot);
    ['corner-tl', 'corner-tr', 'corner-br', 'corner-bl'].forEach((cls) => {
      const c = document.createElement('div');
      c.className = 'target-cursor-corner ' + cls;
      c.style.borderColor = opts.cursorColor;
      cursor.appendChild(c);
    });
    document.body.appendChild(cursor);

    const corners = cursor.querySelectorAll('.target-cursor-corner');
    let containingBlock = getContainingBlock(cursor);
    const getOffset = () => getContainingBlockOffset(containingBlock);

    const useZone = !!opts.zoneSelector;
    const zones = useZone ? Array.prototype.slice.call(document.querySelectorAll(opts.zoneSelector)) : [];

    // In zone mode we never touch the global cursor — only hide it within zones.
    const originalCursor = document.body.style.cursor;
    if (opts.hideDefaultCursor && !useZone) document.body.style.cursor = 'none';

    // If zoned but no zone elements exist on this page, do nothing at all.
    if (useZone && zones.length === 0) {
      cursor.remove();
      return function () {};
    }

    let activeTarget = null;
    let currentLeaveHandler = null;
    let resumeTimeout = null;
    let spinTl = null;
    let targetCornerPositions = null;
    const activeStrength = { current: 0 };

    const initialOffset = getOffset();
    gsap.set(cursor, {
      xPercent: -50,
      yPercent: -50,
      x: window.innerWidth / 2 - initialOffset.x,
      y: window.innerHeight / 2 - initialOffset.y
    });
    if (useZone) gsap.set(cursor, { opacity: 0 });

    function createSpinTimeline() {
      if (spinTl) spinTl.kill();
      spinTl = gsap
        .timeline({ repeat: -1 })
        .to(cursor, { rotation: '+=360', duration: opts.spinDuration, ease: 'none' });
    }
    createSpinTimeline();

    function moveCursor(x, y) {
      const off = getOffset();
      gsap.to(cursor, { x: x - off.x, y: y - off.y, duration: 0.1, ease: 'power3.out' });
    }

    function tickerFn() {
      if (!targetCornerPositions) return;
      const strength = activeStrength.current;
      if (strength === 0) return;
      const cursorX = gsap.getProperty(cursor, 'x');
      const cursorY = gsap.getProperty(cursor, 'y');
      Array.prototype.forEach.call(corners, (corner, i) => {
        const currentX = gsap.getProperty(corner, 'x');
        const currentY = gsap.getProperty(corner, 'y');
        const targetX = targetCornerPositions[i].x - cursorX;
        const targetY = targetCornerPositions[i].y - cursorY;
        const finalX = currentX + (targetX - currentX) * strength;
        const finalY = currentY + (targetY - currentY) * strength;
        const duration = strength >= 0.99 ? (opts.parallaxOn ? 0.2 : 0) : 0.05;
        gsap.to(corner, {
          x: finalX,
          y: finalY,
          duration: duration,
          ease: duration === 0 ? 'none' : 'power1.out',
          overwrite: 'auto'
        });
      });
    }

    const moveHandler = (e) => moveCursor(e.clientX, e.clientY);
    window.addEventListener('mousemove', moveHandler);

    const scrollHandler = () => {
      if (!activeTarget) return;
      const off = getOffset();
      const mouseX = gsap.getProperty(cursor, 'x') + off.x;
      const mouseY = gsap.getProperty(cursor, 'y') + off.y;
      const el = document.elementFromPoint(mouseX, mouseY);
      const stillOver =
        el && (el === activeTarget || el.closest(opts.targetSelector) === activeTarget);
      if (!stillOver && currentLeaveHandler) currentLeaveHandler();
    };
    window.addEventListener('scroll', scrollHandler, { passive: true });

    const mouseDownHandler = () => {
      gsap.to(dot, { scale: 0.7, duration: 0.3 });
      gsap.to(cursor, { scale: 0.9, duration: 0.2 });
    };
    const mouseUpHandler = () => {
      gsap.to(dot, { scale: 1, duration: 0.3 });
      gsap.to(cursor, { scale: 1, duration: 0.2 });
    };
    window.addEventListener('mousedown', mouseDownHandler);
    window.addEventListener('mouseup', mouseUpHandler);

    const enterHandler = (e) => {
      let current = e.target;
      let target = null;
      while (current && current !== document.body) {
        if (current.matches && current.matches(opts.targetSelector)) {
          target = current;
          break;
        }
        current = current.parentElement;
      }
      if (!target) return;
      if (activeTarget === target) return;
      if (activeTarget && currentLeaveHandler) {
        activeTarget.removeEventListener('mouseleave', currentLeaveHandler);
        currentLeaveHandler = null;
      }
      if (resumeTimeout) {
        clearTimeout(resumeTimeout);
        resumeTimeout = null;
      }

      activeTarget = target;
      Array.prototype.forEach.call(corners, (corner) => gsap.killTweensOf(corner, 'x,y'));
      gsap.killTweensOf(cursor, 'rotation');
      if (spinTl) spinTl.pause();
      gsap.set(cursor, { rotation: 0 });

      if (opts.cursorColorOnTarget) {
        gsap.to(corners, { borderColor: opts.cursorColorOnTarget, duration: 0.15, ease: 'power2.out' });
        gsap.to(dot, { backgroundColor: opts.cursorColorOnTarget, duration: 0.15, ease: 'power2.out' });
      }

      const rect = target.getBoundingClientRect();
      const off = getOffset();
      const cursorX = gsap.getProperty(cursor, 'x');
      const cursorY = gsap.getProperty(cursor, 'y');
      targetCornerPositions = [
        { x: rect.left - borderWidth - off.x, y: rect.top - borderWidth - off.y },
        { x: rect.right + borderWidth - cornerSize - off.x, y: rect.top - borderWidth - off.y },
        { x: rect.right + borderWidth - cornerSize - off.x, y: rect.bottom + borderWidth - cornerSize - off.y },
        { x: rect.left - borderWidth - off.x, y: rect.bottom + borderWidth - cornerSize - off.y }
      ];

      gsap.ticker.add(tickerFn);
      gsap.to(activeStrength, { current: 1, duration: opts.hoverDuration, ease: 'power2.out' });

      Array.prototype.forEach.call(corners, (corner, i) => {
        gsap.to(corner, {
          x: targetCornerPositions[i].x - cursorX,
          y: targetCornerPositions[i].y - cursorY,
          duration: 0.2,
          ease: 'power2.out'
        });
      });

      const leaveHandler = () => {
        gsap.ticker.remove(tickerFn);
        targetCornerPositions = null;
        gsap.set(activeStrength, { current: 0, overwrite: true });
        activeTarget = null;

        if (opts.cursorColorOnTarget) {
          gsap.to(corners, { borderColor: opts.cursorColor, duration: 0.15, ease: 'power2.out' });
          gsap.to(dot, { backgroundColor: opts.cursorColor, duration: 0.15, ease: 'power2.out' });
        }

        gsap.killTweensOf(corners, 'x,y');
        const positions = [
          { x: -cornerSize * 1.5, y: -cornerSize * 1.5 },
          { x: cornerSize * 0.5, y: -cornerSize * 1.5 },
          { x: cornerSize * 0.5, y: cornerSize * 0.5 },
          { x: -cornerSize * 1.5, y: cornerSize * 0.5 }
        ];
        const tl = gsap.timeline();
        Array.prototype.forEach.call(corners, (corner, index) => {
          tl.to(corner, { x: positions[index].x, y: positions[index].y, duration: 0.3, ease: 'power3.out' }, 0);
        });

        resumeTimeout = setTimeout(() => {
          if (!activeTarget && spinTl) {
            const currentRotation = gsap.getProperty(cursor, 'rotation');
            const normalized = currentRotation % 360;
            spinTl.kill();
            spinTl = gsap
              .timeline({ repeat: -1 })
              .to(cursor, { rotation: '+=360', duration: opts.spinDuration, ease: 'none' });
            gsap.to(cursor, {
              rotation: normalized + 360,
              duration: opts.spinDuration * (1 - normalized / 360),
              ease: 'none',
              onComplete: () => spinTl && spinTl.restart()
            });
          }
          resumeTimeout = null;
        }, 50);

        target.removeEventListener('mouseleave', leaveHandler);
        currentLeaveHandler = null;
      };

      currentLeaveHandler = leaveHandler;
      target.addEventListener('mouseleave', leaveHandler);
    };
    window.addEventListener('mouseover', enterHandler, { passive: true });

    const resizeHandler = () => {
      containingBlock = getContainingBlock(cursor);
    };
    window.addEventListener('resize', resizeHandler);

    // Zone gating: only reveal the target cursor inside the given zone(s), and
    // hide the default cursor there (never globally).
    const zoneEnter = () => gsap.to(cursor, { opacity: 1, duration: 0.15, ease: 'power2.out' });
    const zoneLeave = () => gsap.to(cursor, { opacity: 0, duration: 0.15, ease: 'power2.out' });
    zones.forEach((z) => {
      z.style.cursor = 'none';
      z.addEventListener('mouseenter', zoneEnter);
      z.addEventListener('mouseleave', zoneLeave);
    });

    // teardown
    return function destroy() {
      gsap.ticker.remove(tickerFn);
      window.removeEventListener('mousemove', moveHandler);
      window.removeEventListener('mouseover', enterHandler);
      window.removeEventListener('scroll', scrollHandler);
      window.removeEventListener('resize', resizeHandler);
      window.removeEventListener('mousedown', mouseDownHandler);
      window.removeEventListener('mouseup', mouseUpHandler);
      if (activeTarget && currentLeaveHandler) activeTarget.removeEventListener('mouseleave', currentLeaveHandler);
      zones.forEach((z) => {
        z.style.cursor = '';
        z.removeEventListener('mouseenter', zoneEnter);
        z.removeEventListener('mouseleave', zoneLeave);
      });
      if (spinTl) spinTl.kill();
      document.body.style.cursor = originalCursor;
      cursor.remove();
    };
  };
})();
