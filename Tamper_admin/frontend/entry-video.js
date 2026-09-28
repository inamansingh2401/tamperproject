(() => {
  'use strict';
  const FAILSAFE_MS = 15000;

  document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('entryVideo');
    const login = document.getElementById('entryLogin');
    const skip = document.getElementById('skipEntry');
    const sound = document.getElementById('soundToggle');
    const password = document.getElementById('password');
    const showPassword = document.getElementById('showPassword');
    if (!video || !login || !skip || !sound) return;

    let failSafe;
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
    function sizeVideoPanel() {
      const scale = Math.max(innerWidth / 1280, innerHeight / 720);
      document.documentElement.style.setProperty('--video-panel-width', `${450 * scale}px`);
      document.documentElement.style.setProperty('--video-panel-height', `${395 * scale}px`);
    }
    sizeVideoPanel();
    addEventListener('resize', sizeVideoPanel);

    function reveal() {
      if (document.body.classList.contains('entry-ready')) return;
      clearTimeout(failSafe);
      document.body.classList.remove('entry-playing');
      document.body.classList.add('entry-ready');
      login.inert = false;
      skip.hidden = true;
    }

    function prepare() {
      clearTimeout(failSafe);
      document.body.classList.remove('entry-ready');
      document.body.classList.add('entry-playing');
      login.inert = true;
      skip.hidden = false;
      failSafe = setTimeout(reveal, FAILSAFE_MS);
    }

    function skipIntro() {
      video.pause();
      if (Number.isFinite(video.duration)) {
        try { video.currentTime = Math.max(0, video.duration - 0.06); } catch (_) {}
      }
      reveal();
    }

    skip.addEventListener('click', skipIntro);
    video.addEventListener('timeupdate', () => {
      if (Number.isFinite(video.duration) && video.currentTime >= video.duration - 1.3) reveal();
    });
    video.addEventListener('ended', reveal);
    video.addEventListener('error', () => {
      video.poster = 'media/cargo-poster.jpg';
      reveal();
    });

    sound.addEventListener('click', async () => {
      if (!video.muted) {
        video.muted = true;
        sound.textContent = 'Replay with sound';
        sound.setAttribute('aria-pressed', 'false');
        return;
      }
      video.currentTime = 0;
      video.muted = false;
      video.volume = 1;
      sound.textContent = 'Mute sound';
      sound.setAttribute('aria-pressed', 'true');
      prepare();
      try { await video.play(); }
      catch (_) {
        video.muted = true;
        sound.textContent = 'Replay with sound';
        sound.setAttribute('aria-pressed', 'false');
        reveal();
      }
    });

    showPassword?.addEventListener('click', () => {
      const visible = password.type === 'text';
      password.type = visible ? 'password' : 'text';
      showPassword.textContent = visible ? 'Show' : 'Hide';
      showPassword.setAttribute('aria-label', visible ? 'Show password' : 'Hide password');
    });

    if (reducedMotion) {
      video.pause();
      video.poster = 'media/cargo-poster.jpg';
      sound.hidden = true;
      reveal();
      return;
    }
    prepare();
    video.muted = true;
    video.play().catch(reveal);
  });
})();
