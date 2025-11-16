import os
import sys
import platform
import shutil
import subprocess
import urllib.request
import zipfile
import tarfile
import stat

sys.stdout.reconfigure(encoding="utf-8")
print(f"当前工作目录: {os.getcwd()}")

# --- 配置 ---
PYTHON_VERSION_TARGET = "3.12.10"  # 目标 Python 版本
PYTHON_BUILD_STANDALONE_RELEASE_TAG = "20250409"

DEST_DIR = os.path.join("install", "python")  # Python 安装的目标目录

# --- 辅助函数 ---

def download_file(url, dest_path):
    """下载文件到指定路径"""
    print(f"正在下载: {url}")
    print(f"到: {dest_path}")
    # 确保目标目录存在
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        with urllib.request.urlopen(url) as response, open(dest_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        print("下载完成。")
    except urllib.error.HTTPError as e:
        print(f"HTTP 错误 {e.code}: {e.reason} (URL: {url})")
        raise
    except urllib.error.URLError as e:
        print(f"URL 错误: {e.reason} (URL: {url})")
        raise
    except Exception as e:
        print(f"下载过程中发生意外错误: {e}")
        raise

def extract_zip(zip_path, dest_dir):
    """解压 ZIP 文件"""
    print(f"正在解压 ZIP: {zip_path} 到 {dest_dir}")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(dest_dir)
    print("ZIP 解压完成。")

def get_python_executable_path(base_dir, os_type):
    """获取已安装 Python 环境中的可执行文件路径"""
    if os_type == "Windows":
        return os.path.join(base_dir, "python.exe")
    elif os_type == "Darwin":  # macOS
        py3_path = os.path.join(base_dir, "bin", "python3")
        py_path = os.path.join(base_dir, "bin", "python")
        if os.path.exists(py3_path):
            return py3_path
        elif os.path.exists(py_path):
            return py_path
        else:
            return None
    return None

def install_pip_and_deps(python_executable, python_install_dir):
    """安装 pip 和项目依赖"""
    if not python_executable or not os.path.exists(python_executable):
        print("错误: Python 可执行文件未找到，无法安装 pip。")
        return False

    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    get_pip_script_path = os.path.join(python_install_dir, "get-pip.py")

    print(f"正在下载 get-pip.py 从 {get_pip_url}")
    try:
        download_file(get_pip_url, get_pip_script_path)
    except Exception as e:
        print(f"下载 get-pip.py 失败: {e}")
        return False

    print("正在使用 get-pip.py 安装 pip...")
    try:
        subprocess.run([python_executable, get_pip_script_path], check=True)
        print("pip 安装成功。")
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"pip 安装失败: {e}")
        return False
    finally:
        if os.path.exists(get_pip_script_path):
            os.remove(get_pip_script_path)

    # 安装项目依赖
    print("正在安装项目依赖...")
    try:
        subprocess.run([
            python_executable, "-m", "pip", "install", 
            "-r", "requirements.txt"
        ], check=True)
        print("项目依赖安装成功。")
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"项目依赖安装失败: {e}")
        return False

    return True

def setup_windows_python():
    """设置 Windows 嵌入式 Python"""
    os_arch = platform.machine()
    processor_identifier = os.environ.get("PROCESSOR_IDENTIFIER", "")

    # 检查是否为ARM64处理器
    if "ARMv8" in processor_identifier or "ARM64" in processor_identifier:
        print(f"检测到ARM64处理器: {processor_identifier}")
        os_arch = "ARM64"

    # 映射架构
    arch_mapping = {
        "AMD64": "amd64",
        "x86_64": "amd64", 
        "ARM64": "arm64",
        "aarch64": "arm64",
    }
    win_arch_suffix = arch_mapping.get(os_arch, os_arch.lower())

    if win_arch_suffix not in ["amd64", "arm64"]:
        print(f"错误: 不支持的Windows架构: {os_arch} -> {win_arch_suffix}")
        return False

    print(f"使用Windows架构: {os_arch} -> {win_arch_suffix}")

    # 下载嵌入式 Python
    download_url = f"https://www.python.org/ftp/python/{PYTHON_VERSION_TARGET}/python-{PYTHON_VERSION_TARGET}-embed-{win_arch_suffix}.zip"
    zip_filename = f"python-{PYTHON_VERSION_TARGET}-embed-{win_arch_suffix}.zip"
    zip_filepath = os.path.join(DEST_DIR, zip_filename)

    try:
        download_file(download_url, zip_filepath)
        extract_zip(zip_filepath, DEST_DIR)
    except Exception as e:
        print(f"Windows Python 下载或解压失败: {e}")
        return False
    finally:
        if os.path.exists(zip_filepath):
            os.remove(zip_filepath)

    # 修改 ._pth 文件以启用标准库导入
    version_nodots = PYTHON_VERSION_TARGET.replace(".", "")[:3]
    pth_filename_pattern = f"python{version_nodots}._pth"

    pth_file_path = os.path.join(DEST_DIR, pth_filename_pattern)
    if not os.path.exists(pth_file_path):
        found_pth_files = [
            f for f in os.listdir(DEST_DIR)
            if f.startswith("python") and f.endswith("._pth")
        ]
        if found_pth_files:
            pth_file_path = os.path.join(DEST_DIR, found_pth_files[0])
        else:
            print(f"错误: 未在 {DEST_DIR} 中找到 ._pth 文件。")
            return False

    print(f"正在修改 ._pth 文件: {pth_file_path}")
    try:
        with open(pth_file_path, "r+", encoding="utf-8") as f:
            content = f.read()
            # 取消注释 import site
            content = content.replace("#import site", "import site")
            content = content.replace("# import site", "import site")
            
            # 添加必要的相对路径
            required_paths = [".", "Lib", "Lib\\site-packages", "DLLs"]
            for p_path in required_paths:
                if p_path not in content.splitlines():
                    content += f"\n{p_path}"
            f.seek(0)
            f.write(content)
            f.truncate()
        print("._pth 文件修改完成。")
    except Exception as e:
        print(f"修改 ._pth 文件失败: {e}")
        return False

    return True

# --- 主逻辑 ---
def main():
    os_type = platform.system()
    print(f"操作系统: {os_type}")
    print(f"目标 Python 版本: {PYTHON_VERSION_TARGET}")
    print(f"目标安装目录: {DEST_DIR}")

    # 检查 Python 是否已经存在
    python_exe_check = get_python_executable_path(DEST_DIR, os_type)
    if python_exe_check and os.path.exists(python_exe_check):
        print(f"Python 似乎已存在于 {DEST_DIR} (找到: {python_exe_check})。")
        if install_pip_and_deps(python_exe_check, DEST_DIR):
            print("Python 和依赖已配置完成。")
            return
        else:
            print("Python 存在但依赖配置失败。将重新安装。")

    if os.path.exists(DEST_DIR):
        print(f"目标目录 {DEST_DIR} 已存在但 Python 未完全配置，将尝试清理并重新安装。")
        try:
            shutil.rmtree(DEST_DIR)
        except OSError as e:
            print(f"清理目录 {DEST_DIR} 失败: {e}。请手动删除后重试。")
            return

    os.makedirs(DEST_DIR, exist_ok=True)
    print(f"已创建目录: {DEST_DIR}")

    success = False
    if os_type == "Windows":
        success = setup_windows_python()
    else:
        print(f"错误: 不支持的操作系统: {os_type}")
        return

    if not success:
        print("Python 环境设置失败。")
        return

    python_executable_final_path = get_python_executable_path(DEST_DIR, os_type)
    if not python_executable_final_path or not os.path.exists(python_executable_final_path):
        print("错误: Python 可执行文件在安装后未找到。")
        return

    print(f"Python 环境已初步设置在: {DEST_DIR}")
    print(f"Python 可执行文件: {python_executable_final_path}")

    # 安装 pip 和项目依赖
    if install_pip_and_deps(python_executable_final_path, DEST_DIR):
        print("嵌入式 Python 环境安装和依赖配置完成。")
    else:
        print("嵌入式 Python 环境安装完成，但依赖配置失败。")

if __name__ == "__main__":
    main()