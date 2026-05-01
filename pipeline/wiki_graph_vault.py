"""Generate an Obsidian vault to natively visualize the Wiki memory graph structure."""

import shutil
from pathlib import Path

from . import paths
from .wiki import load_wiki_memory

def generate_wiki_graph_vault() -> None:
    memory = load_wiki_memory()
    out_dir = paths.OUTPUTS / "wiki_graph_vault"
    
    # Clean previous generation
    if out_dir.exists():
        shutil.rmtree(out_dir)
        
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Create Human and Agent root nodes
    (out_dir / "Human_Findings.md").write_text("# Human Findings\n\nAuthored by humans.", encoding="utf-8")
    (out_dir / "Agent_Findings.md").write_text("# Agent Findings\n\nAuthored by the Wiki Maintainer Agent.", encoding="utf-8")
    
    # Create main index
    (out_dir / "Wiki_Memory.md").write_text("# Wiki Memory\n\n- [[General_Pages]]\n- [[Categories]]\n- [[Human_Findings]]\n- [[Agent_Findings]]\n", encoding="utf-8")
    
    # Create General Pages node
    gen_lines = ["# General Pages\n"]
    for page_id in memory.general_pages.keys():
        gen_lines.append(f"- [[{page_id}]]")
    (out_dir / "General_Pages.md").write_text("\n".join(gen_lines), encoding="utf-8")
    
    # Create Categories node
    cat_lines = ["# Categories\n"]
    for label in memory.category_defs.keys():
        cat_lines.append(f"- [[{label}]]")
    (out_dir / "Categories.md").write_text("\n".join(cat_lines), encoding="utf-8")
    
    def write_findings(page_id, page):
        lines = [f"# {page_id}", "", "This is a wiki page.", ""]
        
        # Human
        for fid in page.human_finding_ids():
            finding_node = f"{page_id}_{fid}"
            lines.append(f"- [[{finding_node}]]")
            content = f"# {finding_node}\n\nBelongs to `[[{page_id}]]` and `[[Human_Findings]]`."
            (out_dir / f"{finding_node}.md").write_text(content, encoding="utf-8")
            
        # Agent
        for fid in page.agent_finding_ids():
            finding_node = f"{page_id}_{fid}"
            lines.append(f"- [[{finding_node}]]")
            content = f"# {finding_node}\n\nBelongs to `[[{page_id}]]` and `[[Agent_Findings]]`."
            (out_dir / f"{finding_node}.md").write_text(content, encoding="utf-8")
            
        (out_dir / f"{page_id}.md").write_text("\n".join(lines), encoding="utf-8")

    # Generate nodes for each general page and its findings
    for page_id, page in memory.general_pages.items():
        write_findings(page_id, page)

    # Generate nodes for each category and its findings
    for label, page in memory.category_defs.items():
        write_findings(label, page)

    print(f"Generated Wiki Graph Vault at {out_dir.relative_to(paths.ROOT)}")
    print("Open this specific folder as a Vault in Obsidian to see the native Graph View of the memory structure!")

def main() -> None:
    generate_wiki_graph_vault()

if __name__ == "__main__":
    main()
