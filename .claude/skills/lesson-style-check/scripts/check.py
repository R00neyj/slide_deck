"""교안(.md)·슬라이드(.html) 문체 후보 검사

CLAUDE.md "AI 티 나는 문체 피하기" 규칙 중 정규식으로 잡을 수 있는 것만 후보로 뽑음
걸린 줄은 후보일 뿐이고, 고칠지는 사람이(또는 에이전트가) 문맥을 보고 정함

검사하지 않는 곳 (줄 번호는 그대로 유지)
- 코드 블록(``` ~~~, 콜아웃 안 "> ```" 포함), 인라인 코드 `...`
- HTML 주석 <!-- -->
- .html 이면 <script> <style> <pre> <code> 와 태그 자체

사용법: python check.py <파일> [<파일> ...]
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def blank_keep_lines(m):
    return "\n" * m.group(0).count("\n")


def strip_md(text):
    text = re.sub(r"<!--.*?-->", blank_keep_lines, text, flags=re.S)
    out, fence = [], None
    for line in text.split("\n"):
        bare = re.sub(r"^\s*(>\s*)*", "", line)
        m = re.match(r"(`{3,}|~{3,})", bare)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            out.append("")
            continue
        if m:
            fence = m.group(1)
            out.append("")
            continue
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"`[^`\n]*`", " ", text)
    text = re.sub(r"\]\([^)\n]*\)", "]", text)  # 링크 주소
    return text


def strip_html(text):
    text = re.sub(r"<!--.*?-->", blank_keep_lines, text, flags=re.S)
    for tag in ("script", "style", "pre", "code", "svg"):
        text = re.sub(rf"<{tag}\b.*?</{tag}>", lambda m: " " + blank_keep_lines(m), text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&"), ("&quot;", '"'), ("&nbsp;", " ")):
        text = text.replace(a, b)
    return text


# (이름, 정규식, 설명) : 한 줄 안에서 찾는 것
LINE_RULES = [
    ("부정 대구", r"아니라|[가-힣]+(?:이|가)?\s*아닌\s|[가-힣]지\s*않고\s|인가[,?]?.{0,30}인가|넘어\s|을 넘어|를 넘어",
     "A가 아니라 B / A 하지 않고 B / A인가 B인가 / A를 넘어 B. 문서 전체에서 한 번까지만"),
    ("연결어미 뒤 쉼표", r"[가-힣](?:고|며|지만|면서|아서|어서|는데|으며|니까),\s",
     "~하고, ~하며, 처럼 연결어미 바로 뒤 쉼표"),
    ("상투구", r"결론적으로|중요함|중요하다|중요합니다|주목할 만|시사하는 바|라고 할 수 있|핵심은|하는 이유임|하는 이유다|다양한|효과적으로|사례|선언|순간",
     "CLAUDE.md 상투구 목록"),
    ("과장", r"획기적|혁신적|마법처럼|중요한 역할",
     "수치나 실제 동작으로 바꾸거나 근거 없으면 문장 삭제"),
    ("번역투", r"에 있어서?|되어지|되어짐|에 의해|가지고 있",
     "~에서 / 능동형 / ~가 만든 / 형용사로"),
    ("말 흐리기", r"것으로 보임|것으로 보인다|수 있을 것|할 수 있을 것으로",
     "완곡 표현 겹침"),
    ("지시형 도입", r"상상해 보세요|상상해보세요",
     "지시형 도입부 금지"),
    ("음슴체 지시문 후보", r"(?:하면|보면|쓰면|누르면|열면) 됨(?:\s|$|\.)|[^가-힣]봄(?:\s|$|\.)|화면을 봄",
     "학생에게 하는 지시가 음슴체로 끝나 어색한지 확인"),
    ("줄 끝 마침표", r"[임함음슴됨봄줌씀둠춤감옴짐]\.\s*\|?\s*$",
     "음슴체 줄 끝 마침표는 빼기. 한 줄 안에서 문장을 나누는 마침표는 괜찮음"),
]

# 문단 단위로 몰려 있을 때만 보는 것 : (이름, 정규식, 문단 내 최소 개수, 설명)
PARA_RULES = [
    ("범용 동사 몰림", r"확대|강화|개선|구축|마련", 2, "실제로 하는 동작으로"),
    ("~적 N 체인", r"[가-힣]적\s+[가-힣]", 3, "~적 N 추상 체인"),
    ("매우·정말", r"매우|정말", 2, "강조 부사 줄이기"),
    ("문두 접속사 몰림", r"(?:^|[.\n]\s*)(?:또한|따라서|즉)\s", 2, "또한·따라서·즉이 한 문단에 몰림"),
    ("대시 몰림", r"—", 2, "대시가 한 문단에 몰림"),
]

ENDING_DUTY = re.compile(r"(?:해야 함|해야 한다|할 필요가 있음|할 필요가 있다)\s*\.?\s*$")


def check(path):
    raw = Path(path).read_text(encoding="utf-8")
    text = strip_html(raw) if path.lower().endswith((".html", ".htm")) else strip_md(raw)
    lines = text.split("\n")
    raw_lines = raw.split("\n")
    hits = []

    for no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        for name, pat, desc in LINE_RULES:
            for m in re.finditer(pat, line):
                hits.append((name, no, m.group(0).strip(), line.strip()))
                break

    # 문단 = 빈 줄로 나뉜 덩어리
    paras, cur, start = [], [], 1
    for no, line in enumerate(lines, 1):
        if line.strip():
            if not cur:
                start = no
            cur.append(line)
        elif cur:
            paras.append((start, "\n".join(cur)))
            cur = []
    if cur:
        paras.append((start, "\n".join(cur)))

    for name, pat, need, desc in PARA_RULES:
        for start, body in paras:
            found = re.findall(pat, body)
            if len(found) >= need:
                hits.append((name, start, f"{len(found)}회", body.strip().split("\n")[0]))

    duty = [(s, b) for s, b in paras if ENDING_DUTY.search(b.strip())]
    if len(duty) >= 2:
        for s, b in duty:
            hits.append(("당위 결말 문단", s, "", b.strip().split("\n")[-1]))

    bold = len(re.findall(r"\*\*[^*\n]+\*\*", text))

    print(f"# {path}")
    rule_desc = {n: d for n, _, d in LINE_RULES} | {n: d for n, _, _, d in PARA_RULES}
    rule_desc["당위 결말 문단"] = "문단마다 ~해야 함으로 끝내지 않음"
    order = [r[0] for r in LINE_RULES] + [r[0] for r in PARA_RULES] + ["당위 결말 문단"]
    total = 0
    for name in order:
        group = [h for h in hits if h[0] == name]
        if not group:
            continue
        total += len(group)
        print(f"\n## {name} ({len(group)}) - {rule_desc[name]}")
        for _, no, hit, ctx in sorted(group, key=lambda h: h[1]):
            ctx = ctx if len(ctx) <= 110 else ctx[:107] + "..."
            print(f"- L{no} [{hit}] {ctx}")
    print(f"\n후보 {total}건 · 굵은 글씨 {bold}곳 (원문 {len(raw_lines)}줄)")
    return total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for i, p in enumerate(sys.argv[1:]):
        if i:
            print("\n" + "-" * 40 + "\n")
        check(p)
