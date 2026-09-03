# ---- 阶段 1：构建前端 ----
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install --registry=https://registry.npmmirror.com
COPY frontend/ ./
RUN npm run build

# ---- 阶段 2：后端运行 ----
FROM python:3.11-slim
WORKDIR /app/backend
# 复制后端代码
COPY backend/ ./
# 复制前端构建产物（由阶段 1 生成），供 app.main / server.py 直接托管
COPY --from=frontend /build/dist /app/frontend/dist
# 安装依赖（FastAPI 全功能模式；缺失时 run.py 自动降级零依赖 server.py）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt
EXPOSE 8000
CMD ["python", "run.py"]
