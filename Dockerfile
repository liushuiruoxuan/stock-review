# ---- 阶段 1：构建前端 ----
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- 阶段 2：后端运行 ----
FROM python:3.11-slim
WORKDIR /app/backend
# 复制后端代码
COPY backend/ ./
# 复制前端构建产物（由阶段 1 生成），供 server.py 直接托管
COPY --from=frontend /build/dist /app/frontend/dist
# 安装 MySQL 驱动
RUN pip install --no-cache-dir PyMySQL
EXPOSE 8000
CMD ["python", "server.py"]
