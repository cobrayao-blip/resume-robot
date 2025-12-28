# Nginx 配置说明

## 目录结构

```
nginx/
├── nginx.prod.conf    # 生产环境Nginx配置
├── ssl/               # SSL证书目录
│   ├── cert.pem      # 证书文件（如果使用自定义证书）
│   └── key.pem       # 私钥文件（如果使用自定义证书）
└── logs/              # Nginx日志目录
```

## SSL证书配置

### 选项1: 使用Let's Encrypt（推荐）

1. 安装Certbot:
```bash
sudo apt install certbot
```

2. 获取证书:
```bash
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com
```

3. 修改 `nginx.prod.conf`:
```nginx
ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
```

4. 在 `docker-compose.prod.yml` 中添加证书卷挂载:
```yaml
volumes:
  - /etc/letsencrypt:/etc/letsencrypt:ro
```

### 选项2: 使用自定义证书

1. 将证书文件复制到 `nginx/ssl/` 目录:
```bash
cp your-cert.pem nginx/ssl/cert.pem
cp your-key.pem nginx/ssl/key.pem
```

2. 确保文件权限正确:
```bash
chmod 600 nginx/ssl/key.pem
chmod 644 nginx/ssl/cert.pem
```

## 配置域名

编辑 `nginx.prod.conf`，将所有 `your-domain.com` 替换为实际域名。

## 日志

Nginx日志会自动保存到 `nginx/logs/` 目录:
- `access.log` - 访问日志
- `error.log` - 错误日志

## 测试配置

```bash
# 测试Nginx配置
docker-compose -f docker-compose.prod.yml exec nginx nginx -t

# 重新加载配置
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

