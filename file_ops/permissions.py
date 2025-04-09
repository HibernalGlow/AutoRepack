"""
文件权限管理模块 - 处理文件权限相关操作
"""
import stat
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def ensure_file_access(file_path: Path) -> bool:
    """
    确保文件可访问，通过修改文件权限和清除只读属性
    
    Args:
        file_path: 要修改权限的文件路径
        
    Returns:
        操作是否成功
    """
    logger.info(f"🔍 开始处理文件权限: {file_path}")
    try:
        if not file_path.exists():
            logger.info(f"❌ 文件不存在: {file_path}")
            return False
            
        # 检查文件当前权限
        try:
            current_mode = file_path.stat().st_mode
            logger.info(f"📝 当前文件权限: {current_mode:o}")
            
            # 检查是否为只读
            is_readonly = not bool(current_mode & stat.S_IWRITE)
            logger.info(f"🔒 文件是否只读: {is_readonly}")
            
            if is_readonly:
                file_path.chmod(current_mode | stat.S_IWRITE)
                logger.info("✅ 已清除只读属性")
        except Exception as e:
            logger.info(f"⚠️ 检查/修改文件属性失败: {file_path}, 错误: {str(e)}")
        
        try:
            # Windows特定的权限处理
            _set_windows_file_permissions(file_path)
        except Exception as e:
            logger.info(f"⚠️ 修改Windows文件权限失败: {file_path}, 错误: {str(e)}")
            # 即使修改Windows权限失败，也继续尝试
            pass
            
        return True
    except Exception as e:
        logger.info(f"❌ 修改文件权限失败: {file_path}, 错误: {str(e)}")
        return False

def _set_windows_file_permissions(file_path: Path) -> None:
    """
    设置Windows文件系统权限
    
    Args:
        file_path: 要修改权限的文件路径
    """
    try:
        # Windows特定的导入
        import win32security
        import win32api
        import win32con
        import ntsecuritycon as con
        
        # 获取当前进程的句柄
        logger.info("🔄 尝试获取进程句柄...")
        ph = win32api.GetCurrentProcess()
        logger.info(f"✅ 成功获取进程句柄: {ph}")
        
        # 打开进程令牌
        logger.info("🔄 尝试打开进程令牌...")
        th = win32security.OpenProcessToken(ph, win32con.TOKEN_QUERY)
        logger.info("✅ 成功打开进程令牌")
        
        # 获取用户SID
        logger.info("🔄 尝试获取用户SID...")
        user = win32security.GetTokenInformation(th, win32security.TokenUser)
        user_sid = user[0]
        logger.info(f"✅ 成功获取用户SID: {user_sid}")
        
        # 获取文件的安全描述符
        logger.info("🔄 尝试获取文件安全描述符...")
        sd = win32security.GetFileSecurity(
            str(file_path), 
            win32security.DACL_SECURITY_INFORMATION
        )
        logger.info("✅ 成功获取文件安全描述符")
        
        # 获取DACL
        logger.info("🔄 尝试获取DACL...")
        dacl = sd.GetSecurityDescriptorDacl()
        if dacl is None:
            logger.info("📝 DACL不存在，创建新的DACL")
            dacl = win32security.ACL()
        else:
            logger.info("✅ 成功获取现有DACL")
        
        # 添加完全控制权限
        logger.info("🔄 尝试添加完全控制权限...")
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION,
            con.FILE_ALL_ACCESS | con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE,
            user_sid
        )
        logger.info("✅ 成功添加完全控制权限")
        
        # 设置新的DACL
        logger.info("🔄 尝试设置新的DACL...")
        sd.SetSecurityDescriptorDacl(1, dacl, 0)
        win32security.SetFileSecurity(
            str(file_path),
            win32security.DACL_SECURITY_INFORMATION,
            sd
        )
        logger.info("✅ 成功设置新的DACL")
        
        # 验证权限
        try:
            # 尝试打开文件进行读写测试
            with open(file_path, 'ab') as f:
                pass
            logger.info("✅ 权限验证成功：文件可以打开进行写入")
        except Exception as e:
            logger.info(f"⚠️ 权限验证失败：无法打开文件进行写入: {e}")
            
    except ImportError:
        logger.info("⚠️ 无法导入Windows特定模块，跳过Windows权限设置")
    except Exception as e:
        logger.info(f"⚠️ 设置Windows文件权限失败: {e}")
        raise 