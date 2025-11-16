# -*- coding: utf-8 -*-

import os
import sys
import subprocess
from pathlib import Path
import logging

# ==============================================================================
# 基本设置
# ==============================================================================

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# 设置项目根目录 (agent的上级目录)
project_root = Path(__file__).resolve().parent.parent

# 将项目根目录加入 sys.path
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 更改工作目录到项目根目录
os.chdir(project_root)
logging.info(f"当前工作目录已设置为: {project_root}")


# ==============================================================================
# 虚拟环境管理 (适用于本地直接运行)
# ==============================================================================

VENV_NAME = ".venv"
VENV_DIR = project_root / VENV_NAME

def is_running_in_our_venv():
    """检查脚本是否在我们自己管理的 .venv 中运行"""
    return Path(sys.executable).resolve().is_relative_to(VENV_DIR.resolve())

def ensure_venv_and_relaunch_if_needed():
    """
    确保虚拟环境存在，如果当前不在该环境中，则创建、安装依赖并重新启动。
    """
    # 如果已在我们的 venv 或 CI 环境中，则跳过
    if is_running_in_our_venv() or os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        logging.debug("已在目标虚拟环境或CI环境中，跳过环境检查。")
        return

    logging.info("未在目标虚拟环境中运行，开始环境自举流程...")

    # 确定虚拟环境中的 Python 解释器路径
    if sys.platform.startswith("win"):
        python_in_venv = VENV_DIR / "Scripts" / "python.exe"
    else:
        python_in_venv = VENV_DIR / "bin" / "python"

    # 如果 venv 或解释器不存在，则创建/修复
    if not python_in_venv.exists():
        logging.info(f"正在创建/修复虚拟环境于: {VENV_DIR}")
        try:
            # 清理可能损坏的旧目录
            if VENV_DIR.exists():
                import shutil
                shutil.rmtree(VENV_DIR)
            # 使用当前外部 Python 创建 venv
            subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True, capture_output=True, text=True)
            logging.info("虚拟环境创建成功。")
        except (subprocess.CalledProcessError, ImportError) as e:
            logging.error(f"创建虚拟环境失败: {getattr(e, 'stderr', e)}")
            sys.exit(1)

    # 在新/现有的 venv 中安装依赖
    req_file = project_root / "requirements.txt"
    if not req_file.exists():
        logging.warning(f"未找到依赖文件: {req_file}，跳过依赖安装。")
    else:
        logging.info(f"正在虚拟环境中安装/更新依赖...")
        try:
            cmd = [str(python_in_venv), "-m", "pip", "install", "-r", str(req_file)]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            for line in iter(process.stdout.readline, ''):
                print(line, end='')
            if process.wait() != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)
            logging.info("依赖安装/更新完成。")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.error(f"在虚拟环境中安装依赖失败: {e}")
            sys.exit(1)

    logging.info(f"环境准备完毕，将使用虚拟环境中的 Python 重新启动脚本...")
    try:
        result = subprocess.run([str(python_in_venv)] + sys.argv, check=False)
        sys.exit(result.returncode)
    except Exception as e:
        logging.error(f"在虚拟环境中重新启动脚本失败: {e}")
        sys.exit(1)


# ==============================================================================
# 核心 Agent 逻辑
# ==============================================================================

def agent_logic():
    """封装启动 AgentServer 的核心逻辑。"""
    
    try:
        from maa.agent.agent_server import AgentServer
        from maa.toolkit import Toolkit
        import mylevelcheck
    except ImportError as e:
        logging.error(f"错误: 无法导入核心模块: {e}")
        logging.error("这可能是由于依赖未能正确安装。请检查之前的日志输出。")
        sys.exit(1)

    Toolkit.init_option(str(project_root))

    if len(sys.argv) < 2:
        logging.error("用法: python main.py <socket_id>")
        logging.error("socket_id 由 AgentIdentifier 提供。")
        sys.exit(1)
        
    socket_id = sys.argv[-1]
    logging.info(f"使用 Socket ID: {socket_id} 启动 AgentServer...")

    try:
        AgentServer.start_up(socket_id)
        logging.info("AgentServer 已启动，等待连接...")
        AgentServer.join()
    except Exception as e:
        logging.error(f"AgentServer 运行期间发生严重错误: {e}")
    finally:
        AgentServer.shut_down()
        logging.info("AgentServer 已关闭。")


# ==============================================================================
# 程序入口
# ==============================================================================

def main():
    # 1. 确保在正确的虚拟环境中运行，如果不是，则创建、安装依赖并重启
    ensure_venv_and_relaunch_if_needed()
    
    # 2. 运行核心业务逻辑 (只有在正确的虚拟环境中才会执行到这里)
    agent_logic()


if __name__ == "__main__":
    main()
