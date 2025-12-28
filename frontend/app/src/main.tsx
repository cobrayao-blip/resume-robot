import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// 抑制已弃用的 DOM Mutation Event 警告
// 这些警告来自第三方库（如 Ant Design）和浏览器扩展，不影响功能
if (typeof window !== 'undefined') {
  const originalAddEventListener = EventTarget.prototype.addEventListener;
  const deprecatedEvents = [
    'DOMNodeInsertedIntoDocument',
    'DOMRemovedFromDocument',
    'DOMNodeInserted',
    'DOMNodeRemoved',
    'DOMSubtreeModified',
    'DOMAttrModified',
    'DOMCharacterDataModified'
  ];
  
  EventTarget.prototype.addEventListener = function(
    type: string,
    listener: EventListenerOrEventListenerObject | null,
    options?: boolean | AddEventListenerOptions
  ) {
    // 静默忽略已弃用的 DOM Mutation Event
    if (deprecatedEvents.includes(type)) {
      return;
    }
    return originalAddEventListener.call(this, type, listener, options);
  };

  // 抑制 Chrome 的 crbug/1173575 警告（非 JS 模块文件已弃用）
  // 这是浏览器内部警告，不影响功能
  const originalWarn = console.warn;
  console.warn = function(...args: any[]) {
    const message = args.join(' ');
    if (message.includes('crbug/1173575') || 
        message.includes('non-JS module files deprecated')) {
      return;
    }
    originalWarn.apply(console, args);
  };
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

