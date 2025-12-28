/** @type {import('tailwindcss').Config} */
export default {
    content: [
      "./index.html",
      "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
      extend: {
        colors: {
          // 专业商务风格配色系统
          primary: {
            50: '#eff6ff',
            100: '#dbeafe',
            200: '#bfdbfe',
            300: '#93c5fd',
            400: '#60a5fa',
            500: '#3b82f6',
            600: '#2563eb',  // 主色调（深蓝）
            700: '#1d4ed8',
            800: '#1e40af',
            900: '#1e3a8a',
          },
          gray: {
            50: '#f9fafb',   // 背景色
            100: '#f3f4f6',  // 浅背景
            200: '#e5e7eb',  // 边框
            300: '#d1d5db',
            400: '#9ca3af',
            500: '#6b7280',  // 次要文本
            600: '#4b5563',
            700: '#374151',  // 主要文本
            800: '#1f2937',
            900: '#111827',  // 标题
          },
          success: '#10b981',
          warning: '#f59e0b',
          error: '#ef4444',
          info: '#3b82f6',
        },
        fontFamily: {
          sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'system-ui', 'sans-serif'],
        },
        boxShadow: {
          'sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
          'DEFAULT': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
          'md': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
          'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
          'xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        },
        spacing: {
          '18': '4.5rem',
          '88': '22rem',
        },
      },
    },
    plugins: [],
    corePlugins: {
      preflight: false,
    }
  }