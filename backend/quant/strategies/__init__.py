"""策略注册表：每个策略一个模块，@register 注册，weights() 产出目标权重矩阵。"""

STRATEGIES = {}


def register(cls):
    STRATEGIES[cls.name] = cls
    return cls


def list_strategies():
    out = []
    for name, cls in STRATEGIES.items():
        out.append({
            "name": name,
            "label": getattr(cls, "label", name),
            "description": getattr(cls, "description", ""),
            "params": getattr(cls, "PARAMS", []),
        })
    return out


def run_strategy(name, close_df, params=None, extra=None):
    """执行策略生成权重矩阵。extra: 策略额外数据（如龙虎榜信号）。"""
    if name not in STRATEGIES:
        raise ValueError("未知策略：%s" % name)
    cls = STRATEGIES[name]
    return cls.weights(close_df, params or {}, extra or {})


from . import ma_cross      # noqa: E402,F401
from . import momentum      # noqa: E402,F401
from . import dragon_follow  # noqa: E402,F401
