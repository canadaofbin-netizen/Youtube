import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


master_path = "BCI_Shorts_Channel/news/2026-10-02_news_hunt.md"
assert os.path.exists(master_path), "Master file does not exist!"

with open(master_path, "r", encoding="utf-8") as f:
    text = f.read()

lines = text.splitlines()
print(f"Total lines in master file: {len(lines)}")
print(f"Total size in master file: {os.path.getsize(master_path):,} bytes")

# 1. Check for all 100 card headers
cards = re.findall(r"^### (\d{2,3})\. (.+)$", text, re.MULTILINE)
print(f"Total cards found matching header pattern: {len(cards)}")
assert len(cards) == 100, f"Expected 100 cards, got {len(cards)}"

# 2. Verify card sequence
for idx, (rank_str, title) in enumerate(cards, 1):
    rank = int(rank_str)
    assert rank == idx, f"Rank mismatch: expected {idx}, got {rank}"

# 3. Check required sections across the document
required_sections = [
    "**1. 핵심 요약 (Core Facts):**",
    "**2. 신비한 건축사전식 역설 훅 (Paradox Hook):**",
    "**3. 3D 절개 단면 비주얼 힌트 (Cutaway Visual Plan):**",
    "**4. 일상적 물리 비유 (Physical Metaphor):**",
    "**5. 화면 전환 및 편집 컷 계획 (Transition & Cut Plan):**",
    "**6. 톤 적합성 판정:**",
    "**7. 세부 점수표:**"
]

for sec in required_sections:
    count = text.count(sec)
    print(f"Section '{sec}' count: {count}")
    assert count == 100, f"Section '{sec}' expected 100 times, got {count}"

# 4. Check Master Index Table rows and Anchor Bijectivity
table_entries = re.findall(r'\| \*\*#(\d+)\*\* \| \[([^\]]+)\]\((#[^\)]+)\) \|', text)
print(f"Total Master Index Table rows found: {len(table_entries)}")
assert len(table_entries) == 100, f"Expected 100 TOC entries, got {len(table_entries)}"

anchors_seen = set()
for idx, (t_rank, t_title, t_anchor) in enumerate(table_entries, 1):
    assert int(t_rank) == idx, f"TOC rank mismatch at row {idx}: {t_rank}"
    
    # Anchor must be clean ASCII with no unstripped emojis, symbols or accents
    assert not re.search(r'[\U00010000-\U0010ffff\u2600-\u27bf\u200d,+/:?!\.éà³]', t_anchor), \
        f"Anchor #{idx} has invalid characters: {t_anchor}"
    
    # Must be unique
    assert t_anchor not in anchors_seen, f"Duplicate anchor detected: {t_anchor}"
    anchors_seen.add(t_anchor)
    
    # Target anchor ID must exist as an explicit HTML anchor tag or section anchor in text
    anchor_id = t_anchor[1:]
    target_tag = f'<a id="{anchor_id}"></a>'
    assert target_tag in text, f"Target anchor tag {target_tag} not found in master document!"

print(f"Verified all 100 TOC anchors: 0 broken links, 100% bijective match with <a id='...'> tags.")

# 5. Check modular files
modular_files = [
    "2026-10-02_pillar1_bci_tech.md",
    "2026-10-02_pillar2_brain_news.md",
    "2026-10-02_pillar3_brain_history.md",
    "2026-10-02_pillar4_brain_basics.md",
    "2026-10-02_pillar5_brain_mysteries.md",
    "2026-10-02_pillar6_brain_health.md",
    "2026-10-02_pillar7_bci_ethics.md"
]

for mf in modular_files:
    p = os.path.join("BCI_Shorts_Channel/news", mf)
    assert os.path.exists(p), f"Modular file {p} does not exist!"
    size = os.path.getsize(p)
    with open(p, "r", encoding="utf-8") as f:
        c_lines = len(f.readlines())
    print(f"Verified {mf}: {c_lines} lines, {size:,} bytes")

print("\n--- ALL 100 RESEARCH CARDS, ANCHORS, AND MODULAR FILES 100% VERIFIED ON DISK! ---")
