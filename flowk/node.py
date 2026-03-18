import time
import inspect
from typing import Callable, Any, Optional

from flowk.exceptions import NodeExecutionError

class Node:
    """
    Represents a functional node within the graph.
    Wraps a Python function and robustly invokes it with retries and fallbacks.
    """
    
    def __init__(self, func: Callable, name: Optional[str] = None, retries: int = 0, fallback: Optional[Callable] = None):
        self.func = func
        self.name = name or func.__name__
        self.retries = retries
        self.fallback = fallback

    def execute(self, input_data: Any, state: Any) -> Any:
        """Executes the function sequentially."""
        func_sig = inspect.signature(self.func)
        kwargs = {}
        if "state" in func_sig.parameters:
            kwargs["state"] = state

        last_exception = None
        for attempt in range(self.retries + 1):
            try:
                return self._invoke(self.func, input_data, kwargs, func_sig)
            except Exception as e:
                last_exception = e
                if attempt < self.retries:
                    time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                    continue
        
        return self._handle_fallback(input_data, state, last_exception)

    async def aexecute(self, input_data: Any, state: Any) -> Any:
        """Executes the function asynchronously, utilizing parallel thread pools for sync functions."""
        import asyncio
        func_sig = inspect.signature(self.func)
        kwargs = {}
        if "state" in func_sig.parameters:
            kwargs["state"] = state

        last_exception = None
        for attempt in range(self.retries + 1):
            try:
                if inspect.iscoroutinefunction(self.func):
                    return await self._ainvoke(self.func, input_data, kwargs, func_sig)
                else:
                    return await asyncio.to_thread(self._invoke, self.func, input_data, kwargs, func_sig)
            except Exception as e:
                last_exception = e
                if attempt < self.retries:
                    await asyncio.sleep(0.1 * (2 ** attempt))
                    continue
        
        # Async fallback handling
        if self.fallback:
            try:
                fb_sig = inspect.signature(self.fallback)
                fb_kwargs = {}
                if "state" in fb_sig.parameters:
                    fb_kwargs["state"] = state
                if inspect.iscoroutinefunction(self.fallback):
                    return await self._ainvoke(self.fallback, input_data, fb_kwargs, fb_sig)
                else:
                    return await asyncio.to_thread(self._invoke, self.fallback, input_data, fb_kwargs, fb_sig)
            except Exception as fb_e:
                raise NodeExecutionError(f"Node '{self.name}' failed and fallback also failed: {fb_e}") from fb_e
        
        raise NodeExecutionError(f"Node '{self.name}' failed after {self.retries} retries: {last_exception}") from last_exception

    def _invoke(self, target_func: Callable, input_data: Any, kwargs: dict, sig: inspect.Signature) -> Any:
        """Helper to invoke a sync function."""
        if len(sig.parameters) == 0:
            return target_func()
        elif len(sig.parameters) == 1 and "state" in sig.parameters:
            return target_func(**kwargs)
        elif len(sig.parameters) == 1 and "state" not in sig.parameters:
            return target_func(input_data)
        else:
            return target_func(input_data, **kwargs)

    async def _ainvoke(self, target_func: Callable, input_data: Any, kwargs: dict, sig: inspect.Signature) -> Any:
        """Helper to invoke an async coroutine."""
        if len(sig.parameters) == 0:
            return await target_func()
        elif len(sig.parameters) == 1 and "state" in sig.parameters:
            return await target_func(**kwargs)
        elif len(sig.parameters) == 1 and "state" not in sig.parameters:
            return await target_func(input_data)
        else:
            return await target_func(input_data, **kwargs)

    def _handle_fallback(self, input_data: Any, state: Any, last_exception: Exception) -> Any:
        if self.fallback:
            try:
                fb_sig = inspect.signature(self.fallback)
                fb_kwargs = {}
                if "state" in fb_sig.parameters:
                    fb_kwargs["state"] = state
                
                return self._invoke(self.fallback, input_data, fb_kwargs, fb_sig)
            except Exception as fb_e:
                raise NodeExecutionError(f"Node '{self.name}' failed and fallback also failed: {fb_e}") from fb_e
        
        raise NodeExecutionError(f"Node '{self.name}' failed after {self.retries} retries: {last_exception}") from last_exception

    def __repr__(self):
        return f"<Node name='{self.name}'>"
