// ==UserScript==
// @name         Antigravity <-> Gemini Argon Bridge
// @namespace    https://github.com/google/antigravity
// @version      1.3.0
// @description  Cầu nối tự động giữa Google Antigravity và Gemini 4 Argon trên Gemini Chat (Multiline & Multiturn Fix)
// @author       Antigravity Pair Programmer
// @match        https://gemini.google.com/*
// @include      https://gemini.google.com/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @run-at       document-end
// ==/UserScript==

(function () {
  'use strict';

  console.log('[ArgonBridge] 🔥 Userscript v1.3.0 (Multiline + Multiturn) đã sẵn sàng!');

  const BRIDGE_URL = 'http://127.0.0.1:7890';
  const POLL_INTERVAL_MS = 1500;
  let isProcessing = false;

  // --- UI STATUS BADGE (Trusted Types Safe) ---
  function ensureBadge() {
    let badge = document.getElementById('argon-bridge-badge');
    if (!badge) {
      badge = document.createElement('div');
      badge.id = 'argon-bridge-badge';
      Object.assign(badge.style, {
        position: 'fixed',
        top: '16px',
        right: '150px',
        zIndex: '2147483647',
        padding: '6px 14px',
        borderRadius: '20px',
        fontSize: '12px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontWeight: '700',
        color: '#ffffff',
        backgroundColor: '#1f2937',
        border: '1px solid #374151',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        transition: 'all 0.3s ease',
        userSelect: 'none',
        pointerEvents: 'auto',
        cursor: 'pointer'
      });

      const dot = document.createElement('span');
      dot.id = 'argon-dot';
      Object.assign(dot.style, {
        width: '10px',
        height: '10px',
        borderRadius: '50%',
        background: '#ef4444',
        display: 'inline-block'
      });

      const label = document.createElement('span');
      label.id = 'argon-text';
      label.textContent = 'Argon Bridge: Đang kết nối...';

      badge.appendChild(dot);
      badge.appendChild(label);
      document.documentElement.appendChild(badge);
    }
    return badge;
  }

  function updateStatus(status, text, color) {
    ensureBadge();
    const dot = document.getElementById('argon-dot');
    const label = document.getElementById('argon-text');
    if (dot) dot.style.background = color;
    if (label) label.textContent = text;
  }

  // --- HTTP HELPER WITH GM_xmlhttpRequest ---
  function bridgeRequest(method, endpoint, data = null) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: method,
        url: `${BRIDGE_URL}${endpoint}`,
        headers: { 'Content-Type': 'application/json' },
        data: data ? JSON.stringify(data) : null,
        timeout: 4000,
        onload: (res) => {
          try {
            const json = JSON.parse(res.responseText);
            resolve(json);
          } catch (e) {
            resolve({ raw: res.responseText });
          }
        },
        onerror: (err) => reject(err),
        ontimeout: () => reject(new Error('Timeout'))
      });
    });
  }

  // --- DOM SELECTORS & ACTIONS ---
  function findEditor() {
    return (
      document.querySelector('rich-textarea div[contenteditable="true"]') ||
      document.querySelector('div[contenteditable="true"][role="textbox"]') ||
      document.querySelector('rich-textarea p') ||
      document.querySelector('div[contenteditable="true"]')
    );
  }

  function findSendButton() {
    return (
      document.querySelector('button[aria-label*="Send message" i]') ||
      document.querySelector('button[aria-label*="Gửi tin nhắn" i]') ||
      document.querySelector('button[aria-label*="Send" i]') ||
      document.querySelector('button[aria-label*="Gửi" i]') ||
      document.querySelector('button.send-button') ||
      document.querySelector('rich-textarea ~ button') ||
      document.querySelector('button[jsname="send"]')
    );
  }

  function isGenerating() {
    const stopBtn =
      document.querySelector('button[aria-label*="Stop" i]') ||
      document.querySelector('button[aria-label*="Dừng" i]') ||
      document.querySelector('button[aria-label*="stop response" i]');
    return !!(stopBtn && stopBtn.offsetParent !== null);
  }

  function getResponseElements() {
    return document.querySelectorAll('message-content, model-response, .model-response-text, .response-container-content');
  }

  async function pasteAndSubmitPrompt(promptText) {
    const editor = findEditor();
    if (!editor) throw new Error('Không tìm thấy khung nhập tin nhắn của Gemini!');

    editor.focus();

    // 1. Thử dán bằng DataTransfer Paste Event (Hỗ trợ toàn diện văn bản nhiều dòng)
    let pasteSucceeded = false;
    try {
      const dt = new DataTransfer();
      dt.setData('text/plain', promptText);
      const pasteEvent = new ClipboardEvent('paste', {
        bubbles: true,
        cancelable: true,
        clipboardData: dt
      });
      pasteSucceeded = editor.dispatchEvent(pasteEvent);
    } catch (e) {
      console.warn('[ArgonBridge] DataTransfer paste failed:', e);
    }

    // 2. Fallback chèn DOM dạng paragraph nếu paste event bị chặn
    if (!editor.innerText || editor.innerText.trim().length === 0) {
      while (editor.firstChild) {
        editor.removeChild(editor.firstChild);
      }
      const lines = promptText.split('\n');
      for (const line of lines) {
        const p = document.createElement('p');
        p.textContent = line || '';
        editor.appendChild(p);
      }
    }

    editor.dispatchEvent(new Event('input', { bubbles: true }));
    editor.dispatchEvent(new Event('change', { bubbles: true }));

    // 3. Chờ nút Send xuất hiện và enabled (tối đa 3 giây)
    let sendBtn = null;
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 100));
      sendBtn = findSendButton();
      if (sendBtn && !sendBtn.disabled && sendBtn.getAttribute('aria-disabled') !== 'true') {
        break;
      }
    }

    if (sendBtn && !sendBtn.disabled && sendBtn.getAttribute('aria-disabled') !== 'true') {
      sendBtn.click();
      console.log('[ArgonBridge] Đã click nút Send!');
    } else {
      // Fallback: Gửi phím Enter trực tiếp vào editor
      console.log('[ArgonBridge] Không thấy nút Send enabled, thử kích hoạt bằng phím Enter...');
      editor.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    }
  }

  async function waitForResponse(initialCount) {
    // Chờ phản hồi mới bắt đầu xuất hiện
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 500));
      if (isGenerating() || getResponseElements().length > initialCount) {
        break;
      }
    }

    updateStatus('answering', 'Argon: Đang suy luận...', '#3b82f6');

    // Chờ đến khi text ngừng sinh (theo dõi chiều dài text ổn định trong 2.5s)
    let lastLength = 0;
    let stableCounter = 0;

    while (true) {
      await new Promise((r) => setTimeout(r, 1000));
      const responses = getResponseElements();
      const currentText = responses.length > 0 ? responses[responses.length - 1].innerText : '';

      if (currentText.length > 0 && currentText.length === lastLength && !isGenerating()) {
        stableCounter++;
        if (stableCounter >= 2) break; // Text không tăng thêm trong 2s và không còn cờ stop
      } else {
        lastLength = currentText.length;
        stableCounter = 0;
      }
    }

    await new Promise((r) => setTimeout(r, 1000));
    const responses = getResponseElements();
    if (responses.length === 0) throw new Error('Không tìm thấy element phản hồi');

    return responses[responses.length - 1].innerText;
  }

  // --- MAIN LOOP ---
  async function pollLoop() {
    if (isProcessing) return;

    try {
      const res = await bridgeRequest('GET', '/poll');
      updateStatus('connected', 'Argon Bridge: Sẵn sàng (Idle)', '#10b981');

      if (res && res.has_task && res.task_id) {
        isProcessing = true;
        const taskId = res.task_id;
        const prompt = res.prompt;

        console.log(`[ArgonBridge] Nhận task mới ${taskId} từ Antigravity!`);
        updateStatus('working', `Argon Bridge: Nhận task ${taskId}...`, '#f59e0b');

        const initialCount = getResponseElements().length;
        try {
          await pasteAndSubmitPrompt(prompt);
          console.log('[ArgonBridge] Đã gửi prompt sang Gemini Web. Đang chờ câu trả lời...');
          const replyText = await waitForResponse(initialCount);

          console.log(`[ArgonBridge] Hoàn thành task ${taskId}! Gửi về Antigravity...`);
          updateStatus('sending', 'Argon Bridge: Đang đồng bộ kết quả...', '#8b5cf6');

          await bridgeRequest('POST', '/reply', {
            task_id: taskId,
            reply: replyText
          });
          updateStatus('connected', 'Argon Bridge: Sẵn sàng (Idle)', '#10b981');
        } catch (innerErr) {
          console.error('[ArgonBridge] Lỗi trong quá trình xử lý task:', innerErr);
          await bridgeRequest('POST', '/reply', {
            task_id: taskId,
            reply: `[ERROR] Không thể gửi/nhận từ Gemini Web: ${innerErr.message}`
          });
          updateStatus('connected', 'Argon Bridge: Sẵn sàng (Idle)', '#10b981');
        }
      }
    } catch (err) {
      updateStatus('offline', 'Argon Bridge: Mất kết nối local', '#ef4444');
    } finally {
      isProcessing = false;
    }
  }

  // Khởi tạo
  ensureBadge();
  setInterval(pollLoop, POLL_INTERVAL_MS);
  console.log('[ArgonBridge] ✅ Tampermonkey script v1.3.0 đã kích hoạt.');
})();
