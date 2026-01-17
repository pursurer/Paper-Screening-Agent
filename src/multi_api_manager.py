"""
多 API Key 并行管理器
实现 N×50 并发，负载均衡和故障转移
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Callable, Any
import random


class KeyStatus(Enum):
    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"


@dataclass
class APIKeySlot:
    """单个 API Key 的状态槽"""
    key: str
    status: KeyStatus = KeyStatus.ACTIVE
    semaphore: asyncio.Semaphore = field(default=None)
    active_requests: int = 0
    total_requests: int = 0
    errors: int = 0
    last_error_time: float = 0
    
    def __post_init__(self):
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(50)
    
    def mask_key(self) -> str:
        """返回遮掩后的 Key 用于日志"""
        if len(self.key) > 10:
            return f"{self.key[:6]}...{self.key[-4:]}"
        return "***"


class MultiAPIManager:
    """多 API Key 并行管理器"""
    
    def __init__(self, api_keys: List[str], concurrency_per_key: int = 50):
        self.slots: List[APIKeySlot] = []
        self.lock = asyncio.Lock()
        self.concurrency_per_key = concurrency_per_key
        
        for key in api_keys:
            slot = APIKeySlot(
                key=key.strip(),
                semaphore=asyncio.Semaphore(concurrency_per_key)
            )
            self.slots.append(slot)
        
        print(f"🔑 已初始化 {len(self.slots)} 个 API Key，总并发数: {len(self.slots) * concurrency_per_key}")
    
    async def acquire_slot(self) -> Optional[APIKeySlot]:
        """获取一个可用的 API Key Slot (Least-Connections 策略)"""
        async with self.lock:
            active_slots = [s for s in self.slots if s.status == KeyStatus.ACTIVE]
            
            if not active_slots:
                # 检查是否有 rate_limited 的可以恢复
                rate_limited = [s for s in self.slots if s.status == KeyStatus.RATE_LIMITED]
                if rate_limited:
                    # 等待最早限流的恢复
                    return None
                raise NoAvailableAPIKeyError("所有 API Key 已耗尽")
            
            # 选择活跃请求最少的 Slot
            slot = min(active_slots, key=lambda s: s.active_requests)
            slot.active_requests += 1
            return slot
    
    async def release_slot(self, slot: APIKeySlot, success: bool, error_code: int = None, error_msg: str = None):
        """释放 Slot 并更新状态"""
        async with self.lock:
            slot.active_requests -= 1
            slot.total_requests += 1
            
            if not success:
                slot.errors += 1
                slot.last_error_time = time.time()
                
                if error_code == 429 or (error_msg and "RESOURCE_EXHAUSTED" in error_msg):
                    if "quota" in str(error_msg).lower() or "per_day" in str(error_msg).lower():
                        # 每日配额耗尽
                        slot.status = KeyStatus.EXHAUSTED
                        print(f"⚠️  API Key {slot.mask_key()} 每日配额耗尽，已禁用")
                    else:
                        # 临时限流，30秒后恢复
                        slot.status = KeyStatus.RATE_LIMITED
                        asyncio.create_task(self._recover_slot(slot, delay=30))
                        print(f"⏳ API Key {slot.mask_key()} 临时限流，30秒后恢复")
    
    async def _recover_slot(self, slot: APIKeySlot, delay: int):
        """延迟恢复 Slot 状态"""
        await asyncio.sleep(delay)
        async with self.lock:
            if slot.status == KeyStatus.RATE_LIMITED:
                slot.status = KeyStatus.ACTIVE
                print(f"✅ API Key {slot.mask_key()} 已恢复")
    
    def get_active_count(self) -> int:
        """获取当前可用的 API Key 数量"""
        return sum(1 for s in self.slots if s.status == KeyStatus.ACTIVE)
    
    def get_stats(self) -> str:
        """获取统计信息"""
        lines = ["📊 API Key 状态:"]
        for i, slot in enumerate(self.slots):
            status_icon = {
                KeyStatus.ACTIVE: "🟢",
                KeyStatus.RATE_LIMITED: "🟡", 
                KeyStatus.EXHAUSTED: "🔴"
            }.get(slot.status, "⚪")
            lines.append(f"  {status_icon} Key {i+1} ({slot.mask_key()}): "
                        f"请求={slot.total_requests}, 错误={slot.errors}, "
                        f"活跃={slot.active_requests}")
        return "\n".join(lines)


class NoAvailableAPIKeyError(Exception):
    """所有 API Key 不可用"""
    pass


async def call_with_multi_api(
    manager: MultiAPIManager,
    call_func: Callable,
    *args,
    max_retries: int = 3,
    **kwargs
) -> Any:
    """
    使用多 API 管理器执行调用，支持故障转移
    
    Args:
        manager: MultiAPIManager 实例
        call_func: 异步调用函数，签名为 async def func(api_key, *args, **kwargs)
        max_retries: 最大重试次数
    
    Returns:
        调用结果
    """
    last_error = None
    
    for attempt in range(max_retries):
        slot = await manager.acquire_slot()
        
        if slot is None:
            # 所有 Key 暂时不可用，等待后重试
            await asyncio.sleep(5)
            continue
        
        try:
            async with slot.semaphore:
                result = await call_func(slot.key, *args, **kwargs)
                await manager.release_slot(slot, success=True)
                return result
        except Exception as e:
            error_msg = str(e)
            error_code = 429 if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg else 500
            await manager.release_slot(slot, success=False, error_code=error_code, error_msg=error_msg)
            last_error = e
            
            # 如果还有其他可用的 Key，立即重试
            if manager.get_active_count() > 0:
                continue
            
            # 等待后重试
            await asyncio.sleep(2 ** attempt)
    
    # 所有重试失败
    raise last_error if last_error else NoAvailableAPIKeyError("调用失败")
