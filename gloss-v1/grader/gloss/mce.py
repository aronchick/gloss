"""ECMA-376 Markup Compatibility and Extensibility preprocessing."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from lxml import etree

from gloss.resources import resolve_normative_schema_file

if TYPE_CHECKING:
    from pathlib import Path

MC_NAMESPACE = "http://schemas.openxmlformats.org/markup-compatibility/2006"
ALTERNATE_CONTENT = f"{{{MC_NAMESPACE}}}AlternateContent"
CHOICE = f"{{{MC_NAMESPACE}}}Choice"
FALLBACK = f"{{{MC_NAMESPACE}}}Fallback"
IGNORABLE = f"{{{MC_NAMESPACE}}}Ignorable"
MUST_UNDERSTAND = f"{{{MC_NAMESPACE}}}MustUnderstand"
PROCESS_CONTENT = f"{{{MC_NAMESPACE}}}ProcessContent"
PRESERVE_ELEMENTS = f"{{{MC_NAMESPACE}}}PreserveElements"
PRESERVE_ATTRIBUTES = f"{{{MC_NAMESPACE}}}PreserveAttributes"
MC_ATTRIBUTES = {
    IGNORABLE,
    MUST_UNDERSTAND,
    PROCESS_CONTENT,
    PRESERVE_ELEMENTS,
    PRESERVE_ATTRIBUTES,
}
PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
LOCAL_NAME = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_.-]*|\*)$")


class MCEProfileError(ValueError):
    """Input markup is not processable under the frozen MCE profile."""


def load_understood_namespaces(profile_path: Path | None = None) -> set[str]:
    """Load the exact understood namespace set from the v1 profile."""
    path = resolve_normative_schema_file("mce-profile-v1.json", profile_path)
    profile: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("profile_id") != "gloss-mce-profile-v1":
        raise MCEProfileError(f"Unsupported MCE profile: {path}")
    namespaces = profile.get("understood_namespaces")
    if not isinstance(namespaces, list) or not all(isinstance(value, str) for value in namespaces):
        raise MCEProfileError(f"Malformed understood_namespaces in {path}")
    return set(namespaces)


def preprocess_markup_compatibility(
    root: etree._Element,
    understood_namespaces: set[str] | None = None,
    *,
    preserved_evidence: list[dict[str, str]] | None = None,
) -> etree._Element:
    """Produce the one validation/inspection tree required by Gloss v1.

    Unsupported ``AlternateContent`` with no fallback, malformed QName lists,
    undeclared prefixes, and unsupported ``MustUnderstand`` namespaces are
    fatal. Unsupported ignorable markup is removed or has its children spliced
    exactly as directed. Preserve directives record location evidence but do
    not make unsupported markup visible to XSD validation or semantic scoring.
    """
    understood = (
        load_understood_namespaces() if understood_namespaces is None else understood_namespaces
    )
    evidence = preserved_evidence if preserved_evidence is not None else []
    _resolve_alternate_content(root, understood)
    _process_element(
        root,
        understood,
        evidence,
        ignorable=frozenset(),
        process_content=frozenset(),
        preserve_elements=frozenset(),
        preserve_attributes=frozenset(),
    )
    return root


def _resolve_alternate_content(root: etree._Element, understood: set[str]) -> None:
    while alternate_nodes := [
        node for node in root.iter(ALTERNATE_CONTENT) if node.getparent() is not None
    ]:
        for alternate in alternate_nodes:
            _replace_alternate_content(alternate, understood)


def _replace_alternate_content(alternate: etree._Element, understood: set[str]) -> None:
    parent = alternate.getparent()
    if parent is None:
        raise MCEProfileError("mc:AlternateContent cannot be the package-part root")

    choices: list[tuple[etree._Element, set[str]]] = []
    fallback: etree._Element | None = None
    fallback_seen = False
    for branch in alternate:
        if branch.tag == CHOICE:
            if fallback_seen:
                raise MCEProfileError("mc:Choice cannot follow mc:Fallback")
            requires = _prefix_namespaces(branch, "Requires", required=True)
            choices.append((branch, requires))
        elif branch.tag == FALLBACK:
            if fallback is not None:
                raise MCEProfileError("mc:AlternateContent has more than one mc:Fallback")
            fallback = branch
            fallback_seen = True
        else:
            raise MCEProfileError(f"Unexpected child of mc:AlternateContent: {branch.tag}")
    if not choices:
        raise MCEProfileError("mc:AlternateContent has no mc:Choice")

    selected = next((branch for branch, requires in choices if requires <= understood), fallback)
    if selected is None:
        raise MCEProfileError(
            "mc:AlternateContent has neither a supported mc:Choice nor mc:Fallback"
        )

    index = parent.index(alternate)
    replacements = [deepcopy(child) for child in selected]
    tail = alternate.tail
    parent.remove(alternate)
    for offset, replacement in enumerate(replacements):
        parent.insert(index + offset, replacement)
    if tail:
        if replacements:
            replacements[-1].tail = f"{replacements[-1].tail or ''}{tail}"
        elif index:
            previous = parent[index - 1]
            previous.tail = f"{previous.tail or ''}{tail}"
        else:
            parent.text = f"{parent.text or ''}{tail}"


def _process_element(
    element: etree._Element,
    understood: set[str],
    evidence: list[dict[str, str]],
    *,
    ignorable: frozenset[str],
    process_content: frozenset[str],
    preserve_elements: frozenset[str],
    preserve_attributes: frozenset[str],
) -> None:
    current_ignorable = ignorable | frozenset(_prefix_namespaces(element, IGNORABLE))
    must_understand = _prefix_namespaces(element, MUST_UNDERSTAND)
    unsupported_must_understand = must_understand - understood
    if unsupported_must_understand:
        joined = ", ".join(sorted(unsupported_must_understand))
        raise MCEProfileError(f"Unsupported mc:MustUnderstand namespace(s): {joined}")

    current_process = process_content | frozenset(_qnames(element, PROCESS_CONTENT))
    current_preserve_elements = preserve_elements | frozenset(_qnames(element, PRESERVE_ELEMENTS))
    current_preserve_attributes = preserve_attributes | frozenset(
        _qnames(element, PRESERVE_ATTRIBUTES)
    )

    for attribute in list(element.attrib):
        attribute_name = str(attribute)
        namespace = _namespace(attribute_name)
        if attribute_name in MC_ATTRIBUTES:
            del element.attrib[attribute]
        elif namespace in current_ignorable and namespace not in understood:
            if _matches(attribute_name, current_preserve_attributes):
                evidence.append(
                    {
                        "kind": "attribute",
                        "xpath": element.getroottree().getpath(element),
                        "qname": attribute_name,
                    }
                )
            del element.attrib[attribute]

    index = 0
    while index < len(element):
        child = element[index]
        namespace = _namespace(str(child.tag))
        if namespace in current_ignorable and namespace not in understood:
            if _matches(str(child.tag), current_preserve_elements):
                evidence.append(
                    {
                        "kind": "element",
                        "xpath": child.getroottree().getpath(child),
                        "qname": str(child.tag),
                    }
                )
            if _matches(str(child.tag), current_process):
                replacements = [deepcopy(grandchild) for grandchild in child]
                tail = child.tail
                element.remove(child)
                for offset, replacement in enumerate(replacements):
                    element.insert(index + offset, replacement)
                if tail and replacements:
                    replacements[-1].tail = f"{replacements[-1].tail or ''}{tail}"
                for replacement in replacements:
                    _process_element(
                        replacement,
                        understood,
                        evidence,
                        ignorable=current_ignorable,
                        process_content=current_process,
                        preserve_elements=current_preserve_elements,
                        preserve_attributes=current_preserve_attributes,
                    )
                index += len(replacements)
                continue
            element.remove(child)
            continue
        _process_element(
            child,
            understood,
            evidence,
            ignorable=current_ignorable,
            process_content=current_process,
            preserve_elements=current_preserve_elements,
            preserve_attributes=current_preserve_attributes,
        )
        index += 1


def _prefix_namespaces(
    element: etree._Element,
    attribute: str,
    *,
    required: bool = False,
) -> set[str]:
    raw = element.get(attribute)
    if raw is None:
        if required:
            raise MCEProfileError(f"Missing {attribute} on {element.tag}")
        return set()
    tokens = raw.split()
    if required and not tokens:
        raise MCEProfileError(f"Empty {attribute} on {element.tag}")
    namespaces: set[str] = set()
    for prefix in tokens:
        if PREFIX.fullmatch(prefix) is None:
            raise MCEProfileError(f"Malformed namespace prefix in {attribute}: {prefix!r}")
        namespace = element.nsmap.get(prefix)
        if namespace is None:
            raise MCEProfileError(f"Undeclared namespace prefix in {attribute}: {prefix!r}")
        namespaces.add(namespace)
    return namespaces


def _qnames(element: etree._Element, attribute: str) -> set[str]:
    raw = element.get(attribute)
    if raw is None:
        return set()
    qnames: set[str] = set()
    for token in raw.split():
        if token.count(":") != 1:
            raise MCEProfileError(
                f"Malformed QName in {etree.QName(attribute).localname}: {token!r}"
            )
        prefix, local = token.split(":", 1)
        if PREFIX.fullmatch(prefix) is None or LOCAL_NAME.fullmatch(local) is None:
            raise MCEProfileError(
                f"Malformed QName in {etree.QName(attribute).localname}: {token!r}"
            )
        namespace = element.nsmap.get(prefix)
        if namespace is None:
            raise MCEProfileError(
                f"Undeclared namespace prefix in {etree.QName(attribute).localname}: {prefix!r}"
            )
        qnames.add(f"{{{namespace}}}{local}")
    return qnames


def _namespace(qname: str) -> str:
    return qname[1 : qname.index("}")] if qname.startswith("{") else ""


def _matches(qname: str, patterns: frozenset[str]) -> bool:
    if qname in patterns:
        return True
    namespace = _namespace(qname)
    return f"{{{namespace}}}*" in patterns
