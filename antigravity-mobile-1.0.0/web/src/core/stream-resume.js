/* Переподключение стрима состояния агента после фона и смены сети. */
var STREAM_RESUME_PATH = /StreamAgentStateUpdates/;
var STREAM_RESUME_MIN_HIDDEN_MS = 2000;
var STREAM_RESUME_DEBOUNCE_MS = 400;

var __agStreams = new Set();
var __agHiddenAt = 0;
var __agRestartTimer = null;

function restartAgentStreams(reason) {
  if (__agRestartTimer) return;
  __agRestartTimer = setTimeout(function () {
    __agRestartTimer = null;
    var list = Array.from(__agStreams);
    for (var i = 0; i < list.length; i++) {
      var entry = list[i];
      if (entry.userAborted) continue;
      entry.restarting = reason;
      try { entry.ac.abort(); } catch (e) { /* ignore */ }
    }
  }, STREAM_RESUME_DEBOUNCE_MS);
}

function wrapStreamResponse(res, entry) {
  if (!res || !res.body || typeof res.body.getReader !== 'function') return res;
  var reader = res.body.getReader();
  var body = new ReadableStream({
    pull: function (controller) {
      return reader.read().then(function (r) {
        if (r.done) {
          __agStreams.delete(entry);
          controller.close();
          return;
        }
        controller.enqueue(r.value);
      }, function (err) {
        __agStreams.delete(entry);
        if (entry.restarting && !entry.userAborted) {
          controller.error(new TypeError('stream restarted: ' + entry.restarting));
        } else {
          controller.error(err);
        }
      });
    },
    cancel: function (reason) {
      __agStreams.delete(entry);
      entry.userAborted = true;
      try { entry.ac.abort(); } catch (e) { /* ignore */ }
      try { return reader.cancel(reason); } catch (e) { return undefined; }
    }
  });
  return new Response(body, { status: res.status, statusText: res.statusText, headers: res.headers });
}

function installStreamResume() {
  if (global.__AG_STREAM_RESUME__ || typeof global.fetch !== 'function') return;
  var prevFetch = global.fetch.bind(global);

  global.fetch = function (resource, init) {
    var url = typeof resource === 'string' ? resource : (resource && resource.url);
    var path = rpcPathFrom(url);
    if (!path || !STREAM_RESUME_PATH.test(path)) return prevFetch(resource, init);

    var ac = new AbortController();
    var entry = { ac: ac, userAborted: false, restarting: '' };
    var userSignal = (init && init.signal) || (resource && typeof resource === 'object' && resource.signal) || null;
    if (userSignal) {
      if (userSignal.aborted) {
        entry.userAborted = true;
        ac.abort();
      } else {
        userSignal.addEventListener('abort', function () {
          entry.userAborted = true;
          try { ac.abort(); } catch (e) { /* ignore */ }
        }, { once: true });
      }
    }
    var next = {};
    if (init) {
      for (var k in init) {
        if (Object.prototype.hasOwnProperty.call(init, k)) next[k] = init[k];
      }
    }
    next.signal = ac.signal;
    __agStreams.add(entry);
    return prevFetch(resource, next).then(function (res) {
      return wrapStreamResponse(res, entry);
    }, function (err) {
      __agStreams.delete(entry);
      throw err;
    });
  };

  // Возврат из фона: хост шлёт agy:host-resume, браузер - visibilitychange.
  global.addEventListener('agy:host-resume', function () {
    var hidden = __agHiddenAt ? Date.now() - __agHiddenAt : STREAM_RESUME_MIN_HIDDEN_MS;
    __agHiddenAt = 0;
    if (hidden >= STREAM_RESUME_MIN_HIDDEN_MS) restartAgentStreams('host-resume');
  });
  if (global.document) {
    global.document.addEventListener('visibilitychange', function () {
      if (global.document.visibilityState === 'hidden') {
        __agHiddenAt = Date.now();
      } else if (__agHiddenAt) {
        var hidden = Date.now() - __agHiddenAt;
        __agHiddenAt = 0;
        if (hidden >= STREAM_RESUME_MIN_HIDDEN_MS) restartAgentStreams('visible');
      }
    });
  }
  // Сеть: восстановление связи и смена типа соединения.
  global.addEventListener('online', function () { restartAgentStreams('online'); });
  try {
    var conn = global.navigator && (global.navigator.connection || global.navigator.mozConnection);
    if (conn && typeof conn.addEventListener === 'function') {
      conn.addEventListener('change', function () { restartAgentStreams('network-change'); });
    }
  } catch (e) { /* ignore */ }

  global.__AG_STREAM_RESUME__ = true;
}

installStreamResume();
