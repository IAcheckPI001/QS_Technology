"""Domain errors shared by context stages (ContextLoader, Prune)."""


class ContextBudgetError(RuntimeError):
    """The mandatory context payload cannot fit the configured budget."""


class ContextConfigurationError(RuntimeError):
    """Context/pruning configuration is missing or invalid."""
