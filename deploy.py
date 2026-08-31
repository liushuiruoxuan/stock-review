"""部署脚本：把本地 backend/server.py 与 frontend/dist 推送到服务器容器并重启。

用法：
    set SSHPASS=你的服务器密码        # Windows cmd
    $env:SSHPASS = "你的服务器密码"   # PowerShell
    python deploy.py

若不设置 SSHPASS，脚本会交互式提示输入密码（不会回显、不会写入仓库）。
切勿把密码硬编码进本文件——它会被提交到 Git 远程。
"""
import getpass
import os

import paramiko

host = os.environ.get('DEPLOY_HOST', 'nas.xingtux.cn')
port = int(os.environ.get('DEPLOY_PORT', '10011'))
user = os.environ.get('DEPLOY_USER', 'root')
container = os.environ.get('DEPLOY_CONTAINER', 'stock-review-web-1')

pwd = os.environ.get('SSHPASS')
if not pwd:
    pwd = getpass.getpass(f'{user}@{host}:{port} 密码：')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, port=port, username=user, password=pwd)

# Upload server.py to server /tmp first
local_server = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', 'server.py')
with ssh.open_sftp() as sftp:
    sftp.put(local_server, '/tmp/server_new.py')
print('Uploaded server.py to /tmp/server_new.py')

# Docker cp server.py into container (both /app/ and /app/backend/)
stdin, stdout, stderr = ssh.exec_command(f'docker cp /tmp/server_new.py {container}:/app/server.py')
print(f'docker cp server.py /app/: {stdout.read().decode().strip()} {stderr.read().decode().strip()}')
stdin, stdout, stderr = ssh.exec_command(f'docker cp /tmp/server_new.py {container}:/app/backend/server.py')
print(f'docker cp server.py /app/backend/: {stdout.read().decode().strip()} {stderr.read().decode().strip()}')

# Upload frontend dist
local_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist')
# Clean remote temp
ssh.exec_command('rm -rf /tmp/frontend_dist')
ssh.exec_command('mkdir -p /tmp/frontend_dist/assets')

with ssh.open_sftp() as sftp:
    # Upload index.html
    sftp.put(os.path.join(local_dist, 'index.html'), '/tmp/frontend_dist/index.html')
    # Upload assets
    assets_dir = os.path.join(local_dist, 'assets')
    for fname in os.listdir(assets_dir):
        sftp.put(os.path.join(assets_dir, fname), f'/tmp/frontend_dist/assets/{fname}')
    print(f'Uploaded frontend dist files')

# Docker cp dist into container
stdin, stdout, stderr = ssh.exec_command(
    f'docker exec {container} rm -rf /app/frontend/dist && '
    f'docker cp /tmp/frontend_dist/. {container}:/app/frontend/dist/'
)
print(f'docker cp dist: {stdout.read().decode()} {stderr.read().decode()}')

# Verify files are in place
stdin, stdout, stderr = ssh.exec_command(f'docker exec {container} ls /app/frontend/dist/')
print(f'dist contents: {stdout.read().decode().strip()}')

# Restart container
stdin, stdout, stderr = ssh.exec_command(f'docker restart {container}')
print(f'docker restart: {stdout.read().decode()} {stderr.read().decode()}')

ssh.close()
print('Deploy complete!')
