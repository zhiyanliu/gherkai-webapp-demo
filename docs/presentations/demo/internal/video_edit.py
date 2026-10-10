#!/usr/bin/env python3
"""Assemble the demo from source excerpts, recorded events, footage and narration."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw

from media_paths import HERE, ROOT, WORK, RECORDING, SOURCE, PREPARATION, DECK, FFMPEG, FFPROBE, NODE
FPS = 25
spec = importlib.util.spec_from_file_location("frames", HERE / "video_frames.py")
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)
STAGES = ["需求", "用例", "本机执行", "失败反馈", "云端复验"]
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:])
    return result.stdout


def story():
    return json.loads((HERE / "video-story.json").read_text())


def narration():
    data=story()
    manifest_path=WORK/"narration-manifest.json"
    old=json.loads(manifest_path.read_text()) if manifest_path.exists() else {"pages":[]}
    by_id={p["id"]:p for p in old["pages"]}
    pages=[]
    for index,segment in enumerate(data["segments"],1):
        digest=hashlib.sha256(segment["speech"].encode()).hexdigest()
        existing=by_id.get(segment["id"],{})
        path=(existing["audio_file"] if existing.get("text_sha256")==digest else
              f"audio/{segment['id']}-{digest[:8]}.mp3")
        metadata=(WORK/path).with_suffix(".json")
        if metadata.exists() and "gherkai" in segment["speech"]:
            prior=json.loads(metadata.read_text())
            if prior.get("pronunciation_dict")!={"tone":["gherkai/格儿凯"]}:
                path=f"audio/{segment['id']}-{digest[:8]}-pronunciation.mp3"
        pages.append({"page":index,"id":segment["id"],"text":segment["speech"],
                      "text_sha256":digest,"audio_file":path})
    style={**data["voice"],"region":"china",
           "voice_id":"moss_audio_ab25b6f0-5e3f-11f1-bb38-6e911a02fa3c",
           "pronunciation_dict":{"tone":["gherkai/格儿凯"]}}
    # Preserve the exact API fields of the previously approved voice.
    style.update(old.get("style",{}))
    save(manifest_path,{"style":style,"pronunciation_dict":{"tone":["gherkai/格儿凯"]},"pages":pages})
    text=["# Demo 视频口播与画面安排","",
          "与定版 Deck 配合。视频保留安装、生成、计划、执行与反馈的关键操作；下载和执行等待经剪辑。",
          "生成草案来自独立练习目录；后续业务执行使用仓库中已审阅的固定版本。来源与证据说明见 [维护说明](internal/README.md)。",""]
    for p,segment in zip(pages,data["segments"]):
        text += [f"## {p['page']:02d} · {segment['title']}",
                 f"画面：Deck 第 {segment['page']} 页 / {segment['kind']}。"]
        if segment["kind"] != "deck":
            text += [f"顶部主张：{segment['takeaway']}。",
                     f"窗口来源／执行环境：{segment['detail']}。"]
        text += ["",segment["speech"],""]
    (HERE.parent/"video-script.md").write_text("\n".join(text))
    missing=[p["page"] for p in pages if not (WORK/p["audio_file"]).exists()]
    print("Narration to synthesize: "+",".join(map(str,missing)))


def cells(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1
               for c in ANSI.sub("", text))


def wrap(text, width=102):
    """Soft-wrap source text without dropping characters or splitting shell tokens."""
    result, line = [], ""
    for token in re.findall(r"[A-Za-z0-9_./:@=-]+|.", text):
        if cells(line + token) > width and line:
            result.append(line)
            line = ""
        line += token
    return result + ([line] if line else [])


def soft_wrap(text,width):
    """Reading wraps preserve every source character, including ANSI controls."""
    lines=[];line="";used=0
    for token in re.findall(r"\x1b\[[0-?]*[ -/]*[@-~]|.",text):
        size=cells(token)
        if used+size>width:
            lines.append(line);line="    ";used=4
        line+=token;used+=size
    return lines+[line]


def cast(name):
    path = PREPARATION/name[len("preparation/"):] if name.startswith("preparation/") else SOURCE/name
    records = [json.loads(line) for line in path.read_text().splitlines()]
    text = "".join(item[2] for item in records[1:] if item[1] == "o")
    lines = text.replace("\r\n", "\n").splitlines()
    # End-of-command shell prompt is display context, not program output.
    while lines and (not ANSI.sub("", lines[-1]).strip()
                     or re.fullmatch(r"ubuntu@demo:[^$]*\$\s*",ANSI.sub("",lines[-1]))):
        lines.pop()
    return lines, records


def command(name):
    lines, _ = cast(name)
    actual = ANSI.sub("", lines[0]).split("$ ", 1)[1]
    output, line = [], "$"
    for token in actual.split():
        if cells(line + " " + token) > 105:
            output.append(line)
            line = "  " + token
        else:
            line += " " + token
    output.append(line)
    return output


def file_lines(path, first, last):
    lines = (SOURCE / path).read_text().splitlines()
    return [f"{index:>3}  {line}" for index, line in enumerate(lines, 1) if first <= index <= last]


def prepare():
    """Prepare only source-backed terminal material; no commands are executed."""
    WORK.mkdir(parents=True, exist_ok=True)
    jobs, views = [], {}

    def add(name, lines, *, width=110, highlight=None, style="record"):
        if isinstance(lines, str):
            lines = lines.splitlines()
        assert lines and not any("\ufffd" in line for line in lines), f"Corrupt source excerpt: {name}"
        original_lines=lines
        lines=[];highlight_rows=[]
        for i,line in enumerate(original_lines):
            pieces=soft_wrap(line,width-2)
            if i in (highlight or []):highlight_rows.extend(range(len(lines),len(lines)+len(pieces)))
            lines.extend(pieces)
        cols = width
        rows = max(len(lines) + 1, 8)
        jobs.append({"name": name, "cols": cols, "rows": rows, "fontSize": 22,
                     "content": "\r\n".join(lines)})
        return {"name": name, "visible_cols": width, "line_count": len(lines),
                "highlight": highlight_rows, "style": style,"source_lines":original_lines,
                "rendered_lines": lines}

    def cmd(name, source):
        return add(name, command(source), width=110, style="command")

    def output(name, source, first=1, last=None, width=110, highlight=None):
        lines, _ = cast(source)
        prefix = command(source) + [""] if first > 0 else []
        return add(name, prefix + lines[first:last], width=width,
                   highlight=[row + len(prefix) for row in (highlight or [])])

    def receipt(name, source, lines, *, width=110, highlight=None):
        prefix = command(source) + [""]
        return add(name, prefix + lines, width=width,
                   highlight=[row + len(prefix) for row in (highlight or [])])

    # Installation is an actual isolated install, with progress-only lines omitted.
    cli_lines,_=cast("preparation/terminal/install-cli.cast")
    installed=[line for line in cli_lines
               if re.match(r"\s*\+\s+gherkai(?:-|==)",ANSI.sub("",line))
               or ANSI.sub("",line).startswith("Installed 1 executable")]
    npm_lines,_=cast("preparation/terminal/install-midscene.cast")
    npm_receipt=[line for line in npm_lines if re.search(r"^added \d+ packages",ANSI.sub("",line))]
    views["setup-install"]=[
        cmd("install-cli-command","preparation/terminal/install-cli.cast"),
        receipt("install-cli-receipt","preparation/terminal/install-cli.cast",
                installed,highlight=list(range(len(installed)))),
        cmd("install-midscene-command","preparation/terminal/install-midscene.cast"),
        receipt("install-midscene-receipt","preparation/terminal/install-midscene.cast",
                npm_receipt,highlight=[0]),
    ]
    skill_lines,_=cast("preparation/terminal/install-skill.cast")
    doctor_lines,_=cast("preparation/terminal/doctor.cast")
    doctor_plain=[ANSI.sub("",line) for line in doctor_lines[1:]]
    views["setup-skill"]=[
        cmd("install-skill-command","preparation/terminal/install-skill.cast"),
        receipt("install-skill-output","preparation/terminal/install-skill.cast",skill_lines[1:3]),
        cmd("setup-doctor-command","preparation/terminal/doctor.cast"),
        receipt("setup-doctor-output","preparation/terminal/doctor.cast",doctor_plain,width=156,
            highlight=[i for i,line in enumerate(doctor_plain) if "自检通过" in line]),
    ]
    for view in views["setup-skill"][2:]:
        view["detail"]="CLI + Midscene / Nova Act worker"
    if (PREPARATION/"agent/events.json").exists():
        generation=json.loads((PREPARATION/"agent/events.json").read_text())
        generation_prompt=(PREPARATION/"agent/prompt.txt").read_text().splitlines()
        views["generation-prompt"]=[
            add("generation-input",generation_prompt[:6],style="agent"),
            add("generation-constraints",generation_prompt[6:],style="agent"),
        ]
        writes=[item for event in generation for item in event.get("content",[])
                if item.get("type")=="tool_use" and item.get("name")=="Write"]
        write_lines=[]
        for item in writes:
            path=item.get("input",{}).get("file_path","")
            if "/project/" in path:
                write_lines.append("Write  "+path.split("/project/",1)[1])
        def generated_excerpt(path,first,last):
            lines=(PREPARATION/"project"/path).read_text().splitlines()
            return [f"{i:>3}  {line}" for i,line in enumerate(lines,1) if first<=i<=last]
        helper=(PREPARATION/"project/steps/_result.mts").read_text().splitlines()
        index=next(i for i,line in enumerate(helper,1) if line.startswith("async function expectText("))
        views["generation-output"]=[
            add("generation-written-files",write_lines,style="agent"),
            add("generation-check-code",generated_excerpt("steps/_result.mts",index,index+10),
                width=124,highlight=[6]),
        ]
        views["generation-review"]=[
            add("generation-review-draft",generated_excerpt("features/result.feature",19,31)),
            add("generation-review-repository",file_lines("inputs/features/result.feature",19,34),
                highlight=[2,10]),
        ]
        views["generation-review"][0]["detail"]="生成草案 · features/result.feature"
        views["generation-review"][1]["detail"]="github.com/zhiyanliu/gherkai-webapp-demo/blob/main/features/result.feature"
        views["generation-output"][0]["detail"]="生成目录 · features/ + steps/"
        views["generation-output"][1]["detail"]="生成文件 · steps/_result.mts"
        # Keep successful unit-test output tied to its actual public tool result.
        def successful_test(events,command_prefix,marker):
            calls=[item for event in events for item in event.get("content",[])
                   if item.get("type")=="tool_use" and item.get("name")=="Bash"
                   and item.get("input",{}).get("command","").startswith(command_prefix)]
            for call in calls:
                results=[item for event in events for item in event.get("content",[])
                         if item.get("type")=="tool_result" and item.get("tool_use_id")==call["id"]]
                for result in results:
                    content=result.get("content","")
                    if isinstance(content,list):
                        content="\n".join(x.get("text","") for x in content if x.get("type")=="text")
                    if marker in content:
                        return call["input"]["command"],content
            raise ValueError("No successful recorded test result: "+command_prefix)
        verification=PREPARATION/"agent-verification/events.json"
        if verification.exists():
            node_cmd,node_result=successful_test(generation,"node --test steps/result.test.mts","# fail 0")
            py_cmd,py_result=successful_test(json.loads(verification.read_text()),"uv run pytest steps/test_result.py","24 passed")
            plan_lines,_=cast("preparation/terminal/generated-plan.cast")
            lines=command("preparation/terminal/generated-plan.cast")+plan_lines[1:3]+["","$ "+node_cmd]
            lines += [line for line in node_result.splitlines() if re.match(r"^(# tests|# pass|# fail) ",line)]
            lines += ["","$ "+py_cmd]+py_result.splitlines()[-2:]
            view=add("generation-local-tests",lines,
                     highlight=[i for i,line in enumerate(lines) if "# pass 24" in line or "24 passed" in line])
            view["detail"]="plan + Python / TypeScript 单测"
            views["generation-output"].append(view)

    # Files are shown as file excerpts, not invented shell sessions.
    requirement_path="inputs/docs/product-requirements.md"
    requirement_lines=(SOURCE/requirement_path).read_text().splitlines()
    first=next(i for i,line in enumerate(requirement_lines,1) if line.startswith("### F4"))
    last=next(i for i,line in enumerate(requirement_lines,1) if line.startswith("### F5"))-1
    req=file_lines(requirement_path,first,last)
    highlight=[i for i,line in enumerate(req) if "「再玩一次」按钮" in line]
    views["requirement"] = [add("requirement",req,highlight=highlight)]
    brief1 = file_lines("inputs/docs/briefs/result.md", 9, 20)
    brief2 = file_lines("inputs/docs/briefs/result.md", 22, 35)
    views["brief"] = [add("brief-scope", [x for row in brief1 for x in wrap(row)]),
                      add("brief-split", [x for row in brief2 for x in wrap(row)])]
    views["feature"] = [
        add("feature-first", file_lines("inputs/features/result.feature", 3, 17), highlight=[2]),
        add("feature-follow", file_lines("inputs/features/result.feature", 19, 34), highlight=[0,5,8]),
    ]
    views["english"] = [add("feature-english", file_lines("inputs/features/result.feature", 58, 71), highlight=[0,2])]
    quiz = (SOURCE / "inputs/steps/quiz.mts").read_text().splitlines()
    score_index = next(i for i, line in enumerate(quiz) if '得分为' in line)
    score_registration = [f"{i+1:>3}  {quiz[i]}" for i in range(max(0,score_index-1), min(len(quiz),score_index+5))]
    views["code"] = [
        add("code-registration", score_registration + [""] + file_lines("inputs/steps/_checks.mts", 194, 198)),
        add("code-feedback", file_lines("inputs/steps/_checks.mts", 139, 154), width=128, highlight=[13,14]),
    ]
    # Keep the registration visible through its explanation; the failure branch
    # appears when the revised narration reaches “如果超时仍不符” at 17.21 s.
    views["code"][0]["duration"]=17.2
    views["main-plan"] = [
        cmd("main-plan-command","normal/plan.cast"),
        output("main-plan-scope","normal/plan.cast",1,6,highlight=[0,1,2]),
        output("main-plan-steps","normal/plan.cast",16,22,width=132,highlight=[3,4]),
    ]
    views["normal-run"] = [
        cmd("normal-run-command","normal/run.cast"),
        output("normal-run-start","normal/run.cast",1,14,width=128),
    ]
    views["normal-explain"] = [
        cmd("normal-explain-command","normal/explain.cast"),
        output("normal-explain-scope","normal/explain.cast",1,5,width=120,highlight=[0,1]),
        output("normal-explain-replay","normal/explain.cast",16,22,highlight=[3,4]),
        cmd("normal-click-command","normal/replay-click.cast"),
        output("normal-click-evidence","normal/replay-click.cast",4,10,width=118),
    ]
    views["fault-run"] = [
        cmd("inject-command","fault/inject.cast"),
        output("inject-output","fault/inject.cast",0,None,width=124),
        cmd("fault-run-command","fault/run.cast"),
        output("fault-run-start","fault/run.cast",1,10,width=128),
    ]
    views["fault-explain"] = [
        cmd("fault-explain-command","fault/explain.cast"),
        output("fault-explain-scope","fault/explain.cast",1,5,width=124,highlight=[0,1]),
        output("fault-explain-replay","fault/explain.cast",16,23,width=110,highlight=[4,5]),
    ]
    failure = json.loads((SOURCE / "fault/failure-step.json").read_text())
    # The complete structured response remains in the source archive.
    serialized = json.dumps(failure,ensure_ascii=False,indent=2).splitlines()
    views["failure-json"] = [
        cmd("failure-json-command","fault/failure-step.cast"),
        receipt("failure-json","fault/failure-step.cast",serialized[19:43],width=118,
            highlight=[i-19 for i,line in enumerate(serialized) if 19<=i<43 and any(k in line for k in ['"text"','"message"'])]),
    ]
    views["restore"] = [cmd("restore-command","cloud/restore.cast"),
                        output("restore-output","cloud/restore.cast",0,None,width=124)]
    views["cloud-submit"] = [
        cmd("cloud-plan-command","cloud/plan.cast"),
        output("cloud-plan-main","cloud/plan.cast",1,5,width=120,highlight=[0,1,2]),
        output("cloud-plan-nova","cloud/plan.cast",28,33,width=120,highlight=[1]),
        cmd("cloud-submit-command","cloud/submit.cast"),
        output("cloud-submit-output","cloud/submit.cast",7,8,width=122,highlight=[0]),
    ]
    # The spoken “随后 submit” begins at 7.35 s; show that invocation at 7.32 s,
    # then keep it visible with the returned run ID as the narration explains it.
    for view,seconds in zip(views["cloud-submit"],[1.64,2.68,3.0,2.52]):
        view["duration"]=seconds
    for view in views["cloud-submit"]:
        if view["name"] not in {"cloud-submit-command","cloud-submit-output"}:
            continue
        emphasis="--backend cloud --prefix vfy-"
        for row,line in enumerate(view["rendered_lines"]):
            if not line.strip():
                break
            plain=ANSI.sub("",line)
            if emphasis in plain:
                start=plain.index(emphasis)
                view["highlight_spans"]=[{
                    "row":row,"start":cells(plain[:start]),
                    "end":cells(plain[:start+len(emphasis)]),
                    "label":"云端执行 · 环境前缀 vfy-",
                }]
                break
        assert view.get("highlight_spans"), "Cloud command options are not visible."
    views["cloud-status"] = [
        cmd("cloud-status-command","cloud/status.cast"),
        output("cloud-status-pending","cloud/status.cast",1,8),
        cmd("cloud-wait-command","cloud/wait.cast"),
        output("cloud-status-passed","cloud/wait.cast",1,8,highlight=[4,5]),
    ]
    views["cloud-main"] = [
        cmd("cloud-main-command","cloud/explain-main.cast"),
        output("cloud-main-replay","cloud/explain-main.cast",16,22,highlight=[3,4]),
        output("cloud-main-home","cloud/explain-main.cast",22,29,highlight=[4,5]),
    ]
    views["cloud-nova"] = [
        cmd("cloud-nova-command","cloud/explain-nova.cast"),
        output("cloud-nova-output","cloud/explain-nova.cast",4,16,width=118,highlight=[6,7,8]),
    ]

    # Public Agent records. No hidden reasoning or invented tool results.
    events = json.loads((SOURCE / "agent/events.json").read_text())
    prompt = (SOURCE / "agent/prompt.txt").read_text().splitlines()
    prompt = [x for x in prompt if x.startswith(("先用 gherkai explain","请说明："))]
    views["agent-prompt"] = [add("agent-prompt",[x for line in prompt for x in wrap(line)] ,style="agent")]
    calls = [(event,item) for event in events for item in event.get("content",[]) if item.get("type")=="tool_use"]
    chosen = [(e,it) for e,it in calls if (
        it.get("input",{}).get("command","").startswith("gherkai explain")
        or it.get("input",{}).get("file_path","").endswith(("docs/product-requirements.md","steps/_checks.mts"))
        or "/report/screenshots/" in it.get("input",{}).get("file_path",""))]
    # Retain the actual chronology and public tool names.
    call_groups = []
    for event,item in chosen:
        inp=item["input"]
        value=inp.get("command") or inp.get("file_path")
        call_groups.append([f'[{event["elapsed_s"]:.1f}s] {item["name"]}']+wrap(value,102)+[""])
    views["agent-tools"] = [
        add("agent-tools-1",[line for group in call_groups[:4] for line in group],style="agent"),
        add("agent-tools-2",[line for group in call_groups[4:] for line in group],style="agent"),
    ]
    conclusion=(SOURCE/"agent/conclusion.md").read_text()
    quotes=[
        re.search(r"已证实的缺陷是：[^。]+。",conclusion).group(),
        re.search(r"尚不能确定的是[^。]+。",conclusion).group(),
    ]
    reply_lines=[x for quote in quotes for x in wrap(quote)+[""]]
    plan_event,plan_call=next((e,it) for e,it in calls if it.get("input",{}).get("command","").startswith("gherkai plan "))
    plan_result=next(item for event in events for item in event.get("content",[])
                     if item.get("type")=="tool_result" and item.get("tool_use_id")==plan_call["id"])
    result_content=plan_result.get("content","")
    if isinstance(result_content,list):
        result_content="\n".join(x.get("text","") for x in result_content if x.get("type")=="text")
    result_lines=ANSI.sub("",result_content).splitlines()
    views["agent-result"]=[
        add("agent-reply",reply_lines,style="agent"),
        add("agent-plan-command",wrap("$ "+plan_call["input"]["command"]),style="agent"),
        add("agent-plan-result",wrap("$ "+plan_call["input"]["command"])+[""]+result_lines[:8],
            width=120,style="agent"),
    ]
    save(WORK/"terminal-jobs.json",{"work":str(WORK/"terminals"),"jobs":jobs})
    save(WORK/"views.json",views)
    print(f"Prepared {len(jobs)} source-backed terminal views.")


def draw_terminal(segment,view,index,metrics):
    kind=segment["kind"]
    detail=view.get("detail") or segment["detail"]
    im=frames.shared_frame("terminal",segment["title"],segment["footer"],detail,
        chapter=f'{segment["stage"]:02d} / {STAGES[segment["stage"]-1]}',
        takeaway=segment["takeaway"],
        body_fill=frames.TERMINAL_BG)
    grid=Image.open(WORK/"terminals"/(view["name"]+".png")).convert("RGB")
    m=metrics[view["name"]]
    # Visible columns are an explicit screenshot crop, not modified CLI text.
    grid=grid.crop((0,0,round(grid.width*min(view["visible_cols"],m["cols"])/m["cols"]),grid.height))
    factor=min(1520/grid.width,686/grid.height,1.0)
    size=(round(grid.width*factor),round(grid.height*factor))
    pos=(194,206 if size[1]>450 else 270)
    im.paste(grid.resize(size,Image.Resampling.LANCZOS),pos)
    row_h=size[1]/m["rows"]
    for row in view["highlight"]:
        if row<view["line_count"]:
            box=(pos[0],round(pos[1]+row*row_h),pos[0]+size[0],round(pos[1]+(row+1)*row_h))
            if segment["selection"] not in {"fault-explain","failure-json","fault-run"}:
                frames.selection_band(im,box,accent="#69DACB",fill="#123E32")
            else:
                frames.selection_band(im,box)
    for span in view.get("highlight_spans",[]):
        cell_w=size[0]/view["visible_cols"]
        box=(pos[0]+span["start"]*cell_w,pos[1]+span["row"]*row_h,
             pos[0]+span["end"]*cell_w,pos[1]+(span["row"]+1)*row_h)
        frames.selection_band(im,box,accent="#69DACB",fill="#123E32")
        label_width=round(frames.font(22,bold=True).getlength(span["label"]))+40
        frames.pill(im,((box[0]+box[2])/2-label_width/2,pos[1]-52),span["label"],label_width,
                    color="white",fill="#087F99",size=22,height=36)
    filename=WORK/"frames"/f'{segment["id"]}-{index:02d}.png'
    im.convert("RGB").save(filename)
    return filename


def browser_marks(failed, *, origin=(270,166), scale=(1382/1456,776/818),
                  cropped_top=0, label_y=354):
    im=Image.new("RGBA",(1920,1080))
    for box,label,color,passed in [
        ((510,103,612,151),"得分仍为 10" if failed else "得分已清零",
         "#CF3E6B" if failed else "#087F99",not failed),
        ((858,103,946,151),"已回到第 1 题","#087F99",True),
    ]:
        x1=round(origin[0]+box[0]*scale[0]);x2=round(origin[0]+box[2]*scale[0])
        y1=round(origin[1]+(box[1]-cropped_top)*scale[1])
        y2=round(origin[1]+(box[3]-cropped_top)*scale[1])
        d=ImageDraw.Draw(im)
        d.rectangle((x1,y1,x2-1,y2-1),fill=(16,156,180,48) if passed else (232,77,118,96))
        d.rectangle((x1-9,y1,x1-1,y2-1),fill=color)
        frames.focus_label(im,(x1+x2)/2,label_y,label,color,passed=passed)
    return im


def render(only=None):
    views=json.loads((WORK/"views.json").read_text())
    metrics={x["name"]:x for x in json.loads((WORK/"terminals/terminal-metrics.json").read_text())}
    (WORK/"frames").mkdir(exist_ok=True)
    shots={}
    for segment in story()["segments"]:
        sid=segment["id"];kind=segment["kind"]
        if only and sid not in only:
            continue
        if kind=="deck":
            image=DECK/f'{segment["page"]:02d}.png'
            replacements={
                2:("selected/normal-midscene-result-card.jpeg",(64,247,500,251.5)),
                7:("selected/normal-midscene-replay-after.jpeg",(64,255,629,322)),
                8:("selected/fault-midscene-replay-after.jpeg",(64,255,629,322)),
            }
            if segment["page"] in replacements:
                source,box=replacements[segment["page"]]
                canvas=Image.open(image).convert("RGB")
                evidence=Image.open(SOURCE/source).convert("RGB")
                x,y,width,height=[v*1.5 for v in box]
                scale=min(width/evidence.width,height/evidence.height)
                size=(round(evidence.width*scale),round(evidence.height*scale))
                canvas.paste(evidence.resize(size,Image.Resampling.LANCZOS),
                             (round(x+(width-size[0])/2),round(y+(height-size[1])/2)))
                image=WORK/"frames"/f"{sid}.png";canvas.save(image)
                shots[sid]=[{"image":str(image),"deck_page":segment["page"],"evidence_source":source}]
            else:
                shots[sid]=[{"image":str(image)}]
        elif kind in {"file","terminal","agent"}:
            shots[sid]=[{"image":str(draw_terminal(segment,view,i,metrics)),
                         "source_view":view["name"],
                         **({"duration":view["duration"]} if "duration" in view else {})}
                        for i,view in enumerate(views[segment["selection"]])]
            if segment["selection"]=="fault-explain":
                frames.terminal_frame()
                shots[sid].append({"image":str(frames.WORK/"terminal.png"),"source_view":"approved-failure-focus"})
        else:
            im=frames.shared_frame("browser",segment["title"],segment["footer"],segment["detail"],
                chapter=f'{segment["stage"]:02d} / {STAGES[segment["stage"]-1]}',
                takeaway=segment["takeaway"])
            if kind=="browser-still":
                shots[sid]=[]
                for i,image in enumerate(segment["images"]):
                    canvas=im.copy();source=Image.open(SOURCE/image).convert("RGB")
                    factor=min(1550/source.width,768/source.height)
                    size=(round(source.width*factor),round(source.height*factor))
                    position=((1920-size[0])//2,170)
                    canvas.paste(source.resize(size,Image.Resampling.LANCZOS),position)
                    if image=="selected/normal-midscene-replay-after.jpeg":
                        # The report screenshot excludes 86 px of Chrome UI.
                        # Transform the same source regions as the later video.
                        canvas.alpha_composite(browser_marks(False,origin=position,
                            scale=(size[0]/source.width,size[1]/source.height),
                            cropped_top=86,label_y=position[1]+round(110*factor)))
                    path=WORK/"frames"/f"{sid}-{i:02d}.png";canvas.convert("RGB").save(path)
                    shot={"image":str(path),"source":image}
                    if i<len(segment.get("image_durations",[])):
                        shot["duration"]=segment["image_durations"][i]
                    shots[sid].append(shot)
            else:
                source=RECORDING/"repaired"/segment["video"]
                background=WORK/"frames"/f"{sid}-background.png";im.convert("RGB").save(background)
                first=frames.extract_frame(source,segment["start"])
                canvas=im.copy();canvas.paste(first.resize((1382,776),Image.Resampling.LANCZOS),(270,166))
                path=WORK/"frames"/f"{sid}-first.png";canvas.convert("RGB").save(path)
                shots[sid]=[{"image":str(path),"background":str(background),"video":str(source),
                    "start":segment["start"],"seconds":segment["seconds"]}]
                if sid in {"19-fault-browser","35-cloud-browser"}:
                    overlay=WORK/"frames"/f"{sid}-marks.png"
                    browser_marks(sid=="19-fault-browser").save(overlay)
                    shots[sid][0].update(marks=str(overlay),marks_start=7.2)
    if only and (WORK/"shots.json").exists():
        previous=json.loads((WORK/"shots.json").read_text())
        previous.update(shots)
        save(WORK/"shots.json",previous)
    else:
        save(WORK/"shots.json",shots)
    review=Image.new("RGB",(1920,math.ceil(len(shots)/3)*390),"#E9EDF7")
    for i,(sid,parts) in enumerate(shots.items()):
        x,y=i%3*640,i//3*390
        frames.text(review,(x+12,y+10),sid,19,"#344264",latin=True)
        preview=Image.open(parts[-1]["image"]).convert("RGB").resize((624,351),Image.Resampling.LANCZOS)
        review.paste(preview,(x+8,y+36))
    review.save(WORK/"storyboard.jpg",quality=92)
    print(f"Rendered {sum(map(len,shots.values()))} full-frame views.")


def duration(path):
    return float(run([FFPROBE,"-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(path)]))


def srt_time(seconds):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def subtitle_number_text(text):
    """Use digits for measured values/counts without changing phrases like 下一轮."""
    digits=dict(zip("零〇一二两三四五六七八九",[0,0,1,2,2,3,4,5,6,7,8,9]))

    def number(value):
        total=current=0
        for char in value:
            if char in digits:
                current=digits[char]
            else:
                total+=(current or 1)*{"十":10,"百":100}[char]
                current=0
        return str(total+current)

    numerals="[零〇一二两三四五六七八九十百]+"
    text=re.sub(r"第("+numerals+r")(?=题|组|个场景|次(?:运行|查询))",
                lambda m:"第"+number(m[1]),text)
    units=(r"个 ?(?:任务|场景|引擎|worker|按钮|位置|前置检查)|"
           r"张页面证据|份输入|条英文代表性场景|道题|步|题|分结算页|项检查|件事")
    text=re.sub(r"(?<![同这那哪每另其上下新逐任某第])("+numerals+r")(?="+units+r")",
                lambda m:number(m[1]),text)
    text=re.sub(r"((?:结算)?得分(?:应为|仍是|为|是)|实际为|测试要求仍然是)("+numerals+r")",
                lambda m:m[1]+number(m[2]),text)
    return text.replace("一次打开网页","1次打开网页")


def subtitle_spans(source_text):
    """Break at spoken clauses, keeping complete words and short lead-ins together."""
    punctuation="，。；！？："
    spans=[[m.start(),m.end()] for m in re.finditer(
        r"[^，。；！？：]+(?:[，。；！？：]+|$)",source_text)]
    assert spans and spans[0][0]==0 and spans[-1][1]==len(source_text)
    assert all(a[1]==b[0] for a,b in zip(spans,spans[1:]))
    lead_ins={"接下来","这样","运行前","向下看","至此","现在","注意","先看注册"}
    index=0
    while index<len(spans):
        start,end=spans[index]
        text=source_text[start:end]
        body=text.strip(punctuation+" ")
        short=len(re.sub(r"\W","",body))<6
        forward=text.endswith("：") or body in lead_ins
        if forward and index+1<len(spans):
            spans[index:index+2]=[[start,spans[index+1][1]]]
            continue
        if short and index and source_text[spans[index-1][1]-1] in "，；：":
            spans[index-1:index+1]=[[spans[index-1][0],end]]
            index=max(0,index-1)
            continue
        if short and text.endswith("，") and index+1<len(spans):
            spans[index:index+2]=[[start,spans[index+1][1]]]
            continue
        index+=1
    return spans


def subtitle_cues(subtitles,offset,speed,source_text):
    # A pronunciation replacement can emit several phonemes for one source span.
    # Merge that span so “格 / 儿 / 凯” displays gherkai once, over its full duration.
    words=[]
    for sentence in subtitles:
        for word in sentence.get("timestamped_words",[]):
            if words and (word["word_begin"],word["word_end"]) == (words[-1]["word_begin"],words[-1]["word_end"]):
                words[-1]["time_end"]=word["time_end"]
            else:
                words.append(dict(word))
    cues=[]
    for start,end in subtitle_spans(source_text):
        group=[word for word in words if word["word_end"]>start and word["word_begin"]<end]
        assert group, f"No spoken timestamps for caption: {source_text[start:end]}"
        text=subtitle_number_text(source_text[start:end])
        text=re.sub(r"[，。；！？：、,.!?;:]+$","",text).strip()
        assert len(re.sub(r"\W","",text))>1, f"Orphan subtitle: {text}"
        cues.append((offset+group[0]["time_begin"]/1000/speed,
                     offset+group[-1]["time_end"]/1000/speed,text))
    return cues


def narration_clip(source,target,seconds,speed):
    samples=round(seconds*48000)
    # Trim by sample count after rebuilding timestamps. Timestamp-based atrim
    # after atempo can silently shorten each clip and accumulate A/V drift.
    run([FFMPEG,"-hide_banner","-loglevel","error","-y","-i",str(source),
         "-af",f"aresample=48000,atempo={speed},asetpts=N/SR/TB,adelay=280:all=1,"
               f"apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB",
         "-c:a","pcm_s16le","-ar","48000","-ac","1",str(target)])


def resync():
    timeline=json.loads((WORK/"timeline.json").read_text())
    manifest=json.loads((WORK/"narration-manifest.json").read_text())
    by_id={p["id"]:p for p in manifest["pages"]}
    speed=story()["voice"]["playback_multiplier"]
    for segment in timeline["segments"]:
        sid=segment["id"]
        narration_clip(WORK/by_id[sid]["audio_file"],WORK/"parts"/f"{sid}.wav",segment["duration"],speed)
    run([FFMPEG,"-hide_banner","-loglevel","error","-y","-f","concat","-safe","0",
         "-i",str(WORK/"parts/audio.txt"),"-c","copy",str(WORK/"narration.wav")])
    import wave
    with wave.open(str(WORK/"narration.wav")) as audio:
        assert audio.getnframes()==round(timeline["duration"]*48000),"Narration samples do not match video frames."
    print("Narration and picture durations match exactly.")


def assemble():
    data=story();shots=json.loads((WORK/"shots.json").read_text());speed=data["voice"]["playback_multiplier"]
    manifest=json.loads((WORK/"narration-manifest.json").read_text())
    audio_by_id={p["id"]:p for p in manifest["pages"]}
    parts=WORK/"parts";parts.mkdir(exist_ok=True)
    timeline=[];concat=[];audio_concat=[];cues=[];cursor=0;previous=None;chapters=[]
    for index,segment in enumerate(data["segments"]):
        sid=segment["id"];views=shots[sid];entry=audio_by_id[sid]
        if entry["text_sha256"]!=hashlib.sha256(segment["speech"].encode()).hexdigest():
            raise ValueError(f"Narration hash mismatch: {sid}")
        audio=WORK/entry["audio_file"]
        if not audio.exists():raise ValueError(f"Missing narration: {sid}")
        lead=.28;tail=.42
        clip_seconds=max(duration(audio)/speed+lead+tail,segment.get("seconds",0))
        count=math.ceil(clip_seconds*FPS);clip_seconds=count/FPS
        mode="deck" if segment["kind"]=="deck" else "demo"
        if previous and previous["mode"]!=mode:
            target=parts/f"{index:02d}-flip.mp4"
            frames.flip_clip(previous["last_image"],views[0]["image"],target,reverse=mode=="deck")
            # The small transition has silence; narration starts on the settled view.
            silence=parts/f"{index:02d}-flip.wav"
            run([FFMPEG,"-hide_banner","-loglevel","error","-y",
                 "-f","lavfi","-i","anullsrc=r=48000:cl=mono","-t","0.44",
                 "-c:a","pcm_s16le",str(silence)])
            concat.append(target);audio_concat.append(silence);cursor+=.44
        if not chapters or chapters[-1]["page"]!=segment["page"]:
            chapters.append({"page":segment["page"],"start":cursor,"title":segment["title"]})
        basevideo=parts/f"{sid}-picture.mp4"
        if "video" in views[0]:
            shot=views[0]
            command=[FFMPEG,"-hide_banner","-loglevel","error","-y",
                     "-loop","1","-framerate",str(FPS),"-i",shot["background"],
                     "-ss",str(shot["start"]),"-t",str(shot["seconds"]),"-i",shot["video"]]
            filters=(f"[1:v]scale=1382:776,setsar=1,tpad=stop_mode=clone:stop_duration={clip_seconds}[app];"
                     "[0:v][app]overlay=270:166:shortest=1[base]")
            output_label="[base]"
            if shot.get("marks"):
                command+=["-loop","1","-framerate",str(FPS),"-i",shot["marks"]]
                filters+=f";[2:v]fade=t=in:st={shot['marks_start']}:d=0.16:alpha=1[marks];[base][marks]overlay=0:0[v]"
                output_label="[v]"
            # Preserve real playback speed; freeze only the last real frame for narration.
            run(command+["-filter_complex",filters,"-map",output_label,"-t",str(clip_seconds),"-an","-r",str(FPS),
                         "-c:v","libx264","-preset","fast","-crf","19","-pix_fmt","yuv420p",str(basevideo)])
            last_canvas=Image.open(shot["background"]).convert("RGB")
            last=frames.extract_frame(Path(shot["video"]),shot["start"]+shot["seconds"]-.08)
            last_canvas.paste(last.resize((1382,776),Image.Resampling.LANCZOS),(270,166))
            if shot.get("marks"):
                overlay=Image.open(shot["marks"]).convert("RGBA")
                last_canvas.paste(overlay,(0,0),overlay)
            last_image=WORK/"frames"/f"{sid}-last.png";last_canvas.save(last_image)
        else:
            # Each original command is visible before its result. No fake typing.
            weights=[.65 if v.get("source_view","").endswith("command") else 1 for v in views]
            remaining=count;clips=[]
            for j,(view,weight) in enumerate(zip(views,weights)):
                n=(remaining if j==len(views)-1 else
                   round(view["duration"]*FPS) if "duration" in view else
                   max(1,round(count*weight/sum(weights))))
                assert 0<n<=remaining, f"Invalid shot timing: {sid}/{j}"
                remaining-=n
                target=parts/f"{sid}-{j:02d}.mp4"
                frames.still_clip(Path(view["image"]),target,n/FPS);clips.append(target)
            listing=parts/f"{sid}-images.txt";listing.write_text("".join(f"file '{p.name}'\n" for p in clips))
            run([FFMPEG,"-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(listing),
                 "-c","copy",str(basevideo)])
            last_image=views[-1]["image"]
        combined=parts/f"{sid}.wav"
        narration_clip(audio,combined,clip_seconds,speed)
        concat.append(basevideo);audio_concat.append(combined)
        subtitles=json.loads(audio.with_suffix(".subtitles.json").read_text())
        cues+=subtitle_cues(subtitles,cursor+lead,speed,segment["speech"])
        timeline.append({**segment,"start_time":cursor,"end_time":cursor+clip_seconds,"duration":clip_seconds,
                         "frames":count,"shots":views,"last_image":str(last_image)})
        cursor+=clip_seconds
        previous={"mode":mode,"last_image":str(last_image)}
        print(f"Encoded {sid} ({clip_seconds:.1f}s)",flush=True)
    listing=parts/"complete.txt";listing.write_text("".join(f"file '{p.name}'\n" for p in concat))
    silent_master=WORK/"assembled.mp4"
    run([FFMPEG,"-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(listing),
         "-c","copy","-movflags","+faststart",str(silent_master)])
    audio_listing=parts/"audio.txt";audio_listing.write_text("".join(f"file '{p.name}'\n" for p in audio_concat))
    soundtrack=WORK/"narration.wav"
    run([FFMPEG,"-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(audio_listing),
         "-c","copy",str(soundtrack)])
    subtitle=WORK/"gherkai-demo.srt"
    subtitle.write_text("\n\n".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}"
                        for i,(a,b,text) in enumerate(cues,1))+"\n",encoding="utf-8")
    # Dedicated lower caption area keeps all recorded pixels and the navigation visible.
    ass=WORK/"captions.ass"
    def ass_time(s):
        cs=round(s*100);h,cs=divmod(cs,360000);m,cs=divmod(cs,6000);ss,cs=divmod(cs,100)
        return f"{h}:{m:02}:{ss:02}.{cs:02}"
    header="""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1200
WrapStyle: 2
[V4+ Styles]
Format: Name, FontName, FontSize, PrimaryColor, BackColor, Bold, Italic, Alignment, MarginL, MarginR, MarginV, BorderStyle, Outline, Shadow
Style: Default,Hiragino Sans GB,34,&H00FFFFFF,&H00252D46,0,0,2,70,70,37,1,0,0
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass.write_text(header+"".join(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{text}\n" for a,b,text in cues),encoding="utf-8")
    save(WORK/"timeline.json",{"duration":cursor,"fps":FPS,"segments":timeline,"chapters":chapters,"subtitle_cues":len(cues)})
    chapter_text="# 完整演示视频章节\n\n"+"\n".join(f"- {srt_time(x['start'])[:8]} · 第 {x['page']} 页 · {x['title']}" for x in chapters)
    (WORK/"chapters.md").write_text(chapter_text+"\n")
    mux()


def subtitle_layer(seconds):
    """Render a frame-accurate caption strip using the same available CJK font.

    This also works with FFmpeg builds that do not include the libass filter.
    """
    folder = WORK / "caption-frames"
    folder.mkdir(exist_ok=True)
    total_frames = round(seconds * FPS)
    blank = folder / "blank.png"
    Image.new("RGB", (1920, 120), "#252D46").save(blank)
    events = {0: blank, total_frames: blank}

    def parse_time(value):
        hour, minute, rest = value.split(":")
        return int(hour) * 3600 + int(minute) * 60 + float(rest.replace(",", "."))

    blocks = (WORK / "gherkai-demo.srt").read_text().strip().split("\n\n")
    for index, block in enumerate(blocks):
        lines = block.splitlines()
        start, end = [parse_time(value) for value in lines[1].split(" --> ")]
        value = " ".join(lines[2:])
        image = Image.new("RGB", (1920, 120), "#252D46")
        draw = ImageDraw.Draw(image)
        typeface = frames.font(34)
        bounds = draw.textbbox((0, 0), value, font=typeface, anchor="lt")
        assert bounds[2] < 1780, f"Caption exceeds its readable area: {value}"
        draw.text(((1920 - bounds[2]) / 2, (120 - bounds[3]) / 2),
                  value, font=typeface, fill="white", anchor="lt")
        path = folder / f"{index:03d}.png"
        image.save(path)
        events[max(0, round(start * FPS))] = path
        events[min(total_frames, round(end * FPS))] = blank
    boundaries = sorted(events)
    parts = []
    for start, end in zip(boundaries, boundaries[1:]):
        if end > start:
            parts += [f"file '{events[start].name}'", f"duration {(end-start)/FPS:.3f}"]
    parts.append(f"file '{blank.name}'")
    listing = folder / "captions.txt"
    listing.write_text("\n".join(parts) + "\n")
    output = WORK / "caption-strip.mp4"
    run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-vf", f"fps={FPS}", "-frames:v", str(total_frames),
         "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "17",
         "-pix_fmt", "yuv420p", str(output)])
    assert abs(duration(output) - seconds) < 1 / FPS
    return output


def mux():
    cursor=json.loads((WORK/"timeline.json").read_text())["duration"]
    silent_master=WORK/"assembled.mp4"
    soundtrack=WORK/"narration.wav"
    captions=subtitle_layer(cursor)
    # Normalize the complete narration once, without altering the approved pacing.
    result=subprocess.run([FFMPEG,"-hide_banner","-i",str(soundtrack),"-af","loudnorm=I=-14:TP=-1:LRA=11:print_format=json","-f","null","-"],capture_output=True,text=True,check=True)
    loudness,_=json.JSONDecoder().raw_decode(result.stderr[result.stderr.rfind("{"):])
    norm=(f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={loudness['input_i']}:measured_TP={loudness['input_tp']}:"
          f"measured_LRA={loudness['input_lra']}:measured_thresh={loudness['input_thresh']}:offset={loudness['target_offset']}:linear=true")
    output=WORK/"gherkai-demo.mp4"
    run([FFMPEG,"-hide_banner","-loglevel","error","-y","-i",str(silent_master),"-i",str(soundtrack),
         "-i",str(captions),"-map","[picture]","-map","1:a",
         "-filter_complex",f"[0:v][2:v]vstack,fade=t=out:st={cursor-.1}:d=0.1,tpad=stop_mode=add:stop_duration=0.16:color=black[picture]",
         "-af",norm+",apad=pad_dur=0.16","-c:v","libx264","-preset","fast","-crf","19","-r",str(FPS),
         "-c:a","aac","-b:a","192k","-ar","48000","-t",str(cursor+.16),
         "-movflags","+faststart",str(output)])
    save(WORK/"audio-normalization.json",loudness)
    print(output)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=["prepare","render","assemble","narration","resync","mux"])
    parser.add_argument("--only",nargs="+",help="Render only named segments for visual review.")
    args=parser.parse_args()
    if args.stage=="render":
        render(args.only)
    else:
        globals()[args.stage]()


if __name__=="__main__":
    main()
