"""
Parser for genes.xml and pop.xml (from prior RE — repomix).
"""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))
from paths import get_data_dir  # noqa: E402


@dataclass
class GeneDefinition:
    name: str
    mutation_rate: int
    scale: int
    values: Dict[str, int]
    nucleotide: str

    @staticmethod
    def from_xml(element: ET.Element) -> GeneDefinition:
        attrs = element.attrib
        values = {k: int(attrs[k]) for k in ("g0", "g1", "g2", "g3") if k in attrs}
        return GeneDefinition(
            attrs.get("name", ""),
            int(attrs.get("m", "0")),
            int(attrs.get("s", "0")),
            values,
            attrs.get("n", ""),
        )


@dataclass
class GeneSet:
    genes: List[GeneDefinition] = field(default_factory=list)

    @staticmethod
    def load(file_path: str) -> GeneSet:
        root = ET.parse(file_path).getroot()
        gene_set = GeneSet()
        for gene_elem in root.findall("gene"):
            gene_set.genes.append(GeneDefinition.from_xml(gene_elem))
        return gene_set


@dataclass
class GeneOverride:
    name: str
    values: Dict[str, int]

    @staticmethod
    def from_xml(element: ET.Element) -> GeneOverride:
        attrs = element.attrib
        values = {k: int(attrs[k]) for k in ("p0", "p1", "p2", "p3") if k in attrs}
        return GeneOverride(attrs.get("name", ""), values)


@dataclass
class PopulationVariant:
    name: str
    overrides: List[GeneOverride] = field(default_factory=list)

    @staticmethod
    def from_xml(element: ET.Element) -> PopulationVariant:
        variant = PopulationVariant(element.attrib.get("name", ""))
        for gene_elem in element.findall("gene"):
            variant.overrides.append(GeneOverride.from_xml(gene_elem))
        return variant


@dataclass
class PopulationSet:
    variants: List[PopulationVariant] = field(default_factory=list)

    @staticmethod
    def load(file_path: str) -> PopulationSet:
        root = ET.parse(file_path).getroot()
        pop_set = PopulationSet()
        top_pop = root.find("pop")
        if top_pop is not None:
            pop_set.variants.append(PopulationVariant.from_xml(top_pop))
            for child in top_pop:
                if child.tag == "pop":
                    pop_set.variants.append(PopulationVariant.from_xml(child))
        return pop_set


if __name__ == "__main__":
    data = get_data_dir()
    gs = GeneSet.load(str(data / "genes.xml"))
    ps = PopulationSet.load(str(data / "pop.xml"))
    print(f"genes: {len(gs.genes)}")
    print(f"pop variants: {len(ps.variants)}")
    print(f"first gene: {gs.genes[0].name if gs.genes else 'none'}")
    print(f"variants: {[v.name for v in ps.variants[:5]]}...")
