"""Code generation: turns computation tasks into a self-contained Python script."""

from .code_generator import CodeGenerator, generate_code_from_tasks

__all__ = ["CodeGenerator", "generate_code_from_tasks"]
