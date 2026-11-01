/*
 * sound_alerts.js - Distinct audio notifications for Antigravity:
 * 1. Done / Completed task (Cascade Done)
 * 2. Action / Input required (Questions, permissions, confirmations)
 * 3. Quota exceeded / depleted (Model quota reached, insufficient credits)
 */
(function() {
  if (window.__AG_SOUND_ALERTS__) return;
  window.__AG_SOUND_ALERTS__ = true;

  var SOUND_MAP = {
    done: '/antigravityCascadeDone.mp3',
    cascadeDone: '/antigravityCascadeDone.mp3',
    action: '/antigravityActionRequired.mp3',
    actionRequired: '/antigravityActionRequired.mp3',
    quota: '/antigravityQuotaExceeded.wav',
    quotaExceeded: '/antigravityQuotaExceeded.wav'
  };

  var lastPlayTimes = {};
  var audioCtx = null;

  function getAudioContext() {
    if (!audioCtx) {
      var AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        audioCtx = new AudioContextClass();
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume().catch(function() {});
    }
    return audioCtx;
  }

  // Synthesize distinctive chime fallback with Web Audio API
  function synthSound(type) {
    try {
      var ctx = getAudioContext();
      if (!ctx) return;
      var now = ctx.currentTime;

      if (type === 'quota' || type === 'quotaExceeded') {
        // Double warning alert (587Hz -> 440Hz descending)
        var osc1 = ctx.createOscillator();
        var gain1 = ctx.createGain();
        osc1.type = 'triangle';
        osc1.frequency.setValueAtTime(587.33, now);
        osc1.frequency.setValueAtTime(440.0, now + 0.22);
        gain1.gain.setValueAtTime(0.3, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.65);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(now);
        osc1.stop(now + 0.65);
      } else if (type === 'action' || type === 'actionRequired') {
        // High attention ping (659Hz -> 880Hz)
        var osc2 = ctx.createOscillator();
        var gain2 = ctx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(659.25, now);
        osc2.frequency.exponentialRampToValueAtTime(880.0, now + 0.15);
        gain2.gain.setValueAtTime(0.35, now);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(now);
        osc2.stop(now + 0.5);
      } else {
        // Ascending pleasant chord (C5 -> E5 -> G5)
        [523.25, 659.25, 783.99].forEach(function(freq, idx) {
          var osc = ctx.createOscillator();
          var gain = ctx.createGain();
          osc.type = 'sine';
          osc.frequency.setValueAtTime(freq, now + idx * 0.08);
          gain.gain.setValueAtTime(0.2, now + idx * 0.08);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.4);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(now + idx * 0.08);
          osc.stop(now + idx * 0.08 + 0.4);
        });
      }
    } catch (e) {
      console.debug('[sound_alerts] synth failed', e);
    }
  }

  function playAlert(type) {
    type = type || 'done';
    var now = Date.now();
    // Debounce同一类型声音 (1.5s)
    if (lastPlayTimes[type] && now - lastPlayTimes[type] < 1500) {
      return;
    }
    lastPlayTimes[type] = now;

    var soundFile = SOUND_MAP[type] || SOUND_MAP.done;
    try {
      var audio = new Audio(soundFile);
      audio.volume = 1.0;
      var played = audio.play();
      if (played && typeof played.catch === 'function') {
        played.catch(function() {
          // Fallback to web audio synthesis
          synthSound(type);
        });
      }
    } catch (_) {
      synthSound(type);
    }
  }

  window.__agPlaySound = playAlert;

  // DOM observer for quota events & warnings
  var quotaSeen = false;
  function scanQuotaAlerts(root) {
    if (!root) return;
    try {
      var str = root.textContent || '';
      if (str.indexOf('Квота модели исчерпана') !== -1 ||
          str.indexOf('Model quota reached') !== -1 ||
          str.indexOf('Baseline model quota reached') !== -1 ||
          str.indexOf('Insufficient AI Credits') !== -1 ||
          str.indexOf('quota_exceeded') !== -1) {
        if (!quotaSeen) {
          quotaSeen = true;
          playAlert('quota');
          setTimeout(function() { quotaSeen = false; }, 10000);
        }
      }
    } catch (e) {}
  }

  var observer = new MutationObserver(function(mutations) {
    for (var i = 0; i < mutations.length; i++) {
      var m = mutations[i];
      if (m.addedNodes && m.addedNodes.length > 0) {
        for (var j = 0; j < m.addedNodes.length; j++) {
          scanQuotaAlerts(m.addedNodes[j]);
        }
      }
    }
  });

  if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
  } else {
    document.addEventListener('DOMContentLoaded', function() {
      observer.observe(document.body, { childList: true, subtree: true });
    });
  }

  // Allow unlock on first user tap/click
  var unlock = function() {
    getAudioContext();
    window.removeEventListener('click', unlock);
    window.removeEventListener('touchstart', unlock);
  };
  window.addEventListener('click', unlock, { once: true, passive: true });
  window.addEventListener('touchstart', unlock, { once: true, passive: true });
})();
