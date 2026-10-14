/**
 * TECHPANDA CRM - Universal Audio Waveform Player (waveform-player.js alias)
 * Delegates to the unified window.initWaveformPlayers implementation to prevent
 * any duplicate registration, state collision, or event conflicts.
 */
(function () {
  'use strict';

  if (typeof window.initWaveformPlayers === 'function') {
    window.initWaveformPlayers();
  } else {
    // If audio-player.js was somehow not loaded yet, define it here
    var currentPlayingAudio = null;

    function formatTime(seconds) {
      if (isNaN(seconds) || seconds < 0) return '00:00';
      var mins = Math.floor(seconds / 60);
      var secs = Math.floor(seconds % 60);
      return (mins < 10 ? '0' : '') + mins + ':' + (secs < 10 ? '0' : '') + secs;
    }

    function renderWaveform(canvas, progress, audioSrc) {
      if (!canvas) return;
      var ctx = canvas.getContext('2d');
      var w = canvas.width || 120;
      var h = canvas.height || 24;
      ctx.clearRect(0, 0, w, h);

      var numBars = 36;
      var barWidth = 2.5;
      var gap = (w - (numBars * barWidth)) / (numBars - 1);

      var seed = 42;
      var srcStr = audioSrc || '';
      for (var i = 0; i < srcStr.length; i++) {
        seed = (seed * 31 + srcStr.charCodeAt(i)) % 1000;
      }

      var isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
                   document.body.classList.contains('dark-theme');
      var activeColor = isDark ? '#818cf8' : '#4f46e5';
      var inactiveColor = isDark ? '#334155' : '#cbd5e1';

      for (var b = 0; b < numBars; b++) {
        var barProgress = b / numBars;
        var pseudoRand = Math.sin(seed + b * 0.72) * 0.45 + 0.55;
        var barHeight = Math.max(4, pseudoRand * (h - 6));
        var x = b * (barWidth + gap);
        var y = (h - barHeight) / 2;

        ctx.fillStyle = barProgress <= progress ? activeColor : inactiveColor;
        ctx.beginPath();
        if (typeof ctx.roundRect === 'function') {
          ctx.roundRect(x, y, barWidth, barHeight, 1.5);
        } else {
          ctx.rect(x, y, barWidth, barHeight);
        }
        ctx.fill();
      }
    }

    function updatePlayIcon(playBtn, isPlaying) {
      if (!playBtn) return;
      if (isPlaying) {
        playBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"></rect><rect x="14" y="4" width="4" height="16" rx="1"></rect></svg>';
        playBtn.title = 'Pause';
        playBtn.setAttribute('aria-label', 'Pause');
      } else {
        playBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
        playBtn.title = 'Play';
        playBtn.setAttribute('aria-label', 'Play');
      }
    }

    var init = function () {
      var playerContainers = document.querySelectorAll('.tp-waveform-player:not([data-initialized="true"])');

      playerContainers.forEach(function (container) {
        var audio = container.querySelector('audio');
        var audioSrc = container.getAttribute('data-src');

        if (!audio && audioSrc) {
          audio = document.createElement('audio');
          audio.preload = 'none';
          audio.src = audioSrc;
          audio.style.display = 'none';
          container.appendChild(audio);
        }

        if (!audio) return;

        if (!audio.src) {
          var sourceTag = audio.querySelector('source');
          if (sourceTag && sourceTag.src) {
            audio.src = sourceTag.src;
          } else if (audioSrc) {
            audio.src = audioSrc;
          }
        }

        var playBtn = container.querySelector('.tp-player-btn-play');
        var timeDisplay = container.querySelector('.tp-player-time');
        var speedBtn = container.querySelector('.tp-player-btn-speed');
        var canvas = container.querySelector('.tp-player-canvas');

        if (!playBtn || !canvas) return;

        container.setAttribute('data-initialized', 'true');
        canvas.width = canvas.width || 120;
        canvas.height = canvas.height || 24;

        var srcForWaveform = audio.src || audioSrc || '';
        renderWaveform(canvas, 0, srcForWaveform);

        var speeds = [1.0, 1.25, 1.5, 2.0];
        var speedIndex = 0;

        playBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();

          if (audio.paused) {
            if (currentPlayingAudio && currentPlayingAudio !== audio) {
              currentPlayingAudio.pause();
            }

            var playPromise = audio.play();
            if (playPromise !== undefined) {
              playPromise.then(function () {
                currentPlayingAudio = audio;
                updatePlayIcon(playBtn, true);
                playBtn.classList.remove('has-error');
              }).catch(function (err) {
                console.warn('Playback error:', err);
                updatePlayIcon(playBtn, false);
                if (err.name !== 'AbortError') {
                  playBtn.classList.add('has-error');
                  playBtn.title = 'Unable to play recording. Click to retry or download file.';
                }
              });
            }
          } else {
            audio.pause();
            updatePlayIcon(playBtn, false);
          }
        });

        audio.addEventListener('play', function () {
          currentPlayingAudio = audio;
          updatePlayIcon(playBtn, true);
        });

        audio.addEventListener('pause', function () {
          updatePlayIcon(playBtn, false);
        });

        audio.addEventListener('timeupdate', function () {
          var progress = audio.duration ? (audio.currentTime / audio.duration) : 0;
          renderWaveform(canvas, progress, srcForWaveform);
          if (timeDisplay) {
            timeDisplay.textContent = formatTime(audio.currentTime);
          }
        });

        audio.addEventListener('ended', function () {
          updatePlayIcon(playBtn, false);
          renderWaveform(canvas, 0, srcForWaveform);
          if (timeDisplay) {
            timeDisplay.textContent = formatTime(audio.duration || 0);
          }
          if (currentPlayingAudio === audio) {
            currentPlayingAudio = null;
          }
        });

        audio.addEventListener('loadedmetadata', function () {
          if (timeDisplay && (!audio.currentTime || audio.currentTime === 0)) {
            timeDisplay.textContent = formatTime(audio.duration || 0);
          }
        });

        audio.addEventListener('error', function () {
          console.error('Audio source error:', audio.error);
          updatePlayIcon(playBtn, false);
          playBtn.classList.add('has-error');
          playBtn.title = 'Audio load error. Click to retry or use download link.';
        });

        canvas.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();

          var rect = canvas.getBoundingClientRect();
          var clickX = e.clientX - rect.left;
          var frac = Math.max(0, Math.min(1, clickX / rect.width));

          if (audio.duration && !isNaN(audio.duration)) {
            audio.currentTime = frac * audio.duration;
            renderWaveform(canvas, frac, srcForWaveform);
            if (timeDisplay) {
              timeDisplay.textContent = formatTime(audio.currentTime);
            }
          }
        });

        if (speedBtn) {
          speedBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            speedIndex = (speedIndex + 1) % speeds.length;
            var newSpeed = speeds[speedIndex];
            audio.playbackRate = newSpeed;
            speedBtn.textContent = newSpeed.toFixed(2).replace(/\.00$/, '') + 'x';
          });
        }
      });
    };

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
    window.initWaveformPlayers = init;
  }
})();
