FROM node:18-alpine

WORKDIR /app

# 仅复制依赖清单以缓存安装层
COPY package.json ./

# 安装依赖（其余源码通过挂载提供）
RUN npm install

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]



