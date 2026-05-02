"""Verifies the framework package layout for v1.24."""


def test_framework_modules_importable():
    from mcp_server.composer.framework import (
        intent_source,
        brief,
        knowledge_pack,
        plan_compiler,
        applier,
    )
    assert hasattr(intent_source, "IntentSource")
    assert hasattr(intent_source, "PromptSource")
    assert hasattr(intent_source, "SessionSource")
    assert hasattr(intent_source, "HybridSource")
    assert hasattr(brief, "Brief")
    assert hasattr(brief, "FastBrief")
    assert hasattr(brief, "FullBrief")
    assert hasattr(brief, "DevelopBrief")
    assert hasattr(knowledge_pack, "KnowledgePack")
    assert hasattr(plan_compiler, "PlanCompiler")
    assert hasattr(applier, "Applier")


def test_brief_subclasses_inherit_correctly():
    from mcp_server.composer.framework.brief import Brief, FastBrief, FullBrief, DevelopBrief
    assert issubclass(FastBrief, Brief)
    assert issubclass(FullBrief, Brief)
    assert issubclass(DevelopBrief, Brief)


def test_intent_source_subclasses_inherit_correctly():
    from mcp_server.composer.framework.intent_source import (
        IntentSource, PromptSource, SessionSource, HybridSource,
    )
    assert issubclass(PromptSource, IntentSource)
    assert issubclass(SessionSource, IntentSource)
    assert issubclass(HybridSource, IntentSource)
