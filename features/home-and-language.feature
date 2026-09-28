# 主页与界面语言（需求 F1、F5）。对应简报 docs/briefs/home-and-language.md，需求 docs/product-requirements.md 第 5 节 F1、F5（含文案对照表）。
#
# 引擎：从中文界面进入的场景标 @engine:midscene（切换后页面变英文，Midscene 对语言不限，同一条里两种语言都能判）；
#       以英文界面启动的那条标 @engine:novaact，其 AI 步用英文写（Nova Act 面向英文）。
# 分工：页面标题、切换按钮上的文字、地址栏 lang 参数、刷新页面走确定性 step（steps/home_and_language.py 与
#       steps/home_and_language.mts，两引擎成对）；进度、得分、按题库答对复用 steps/quiz.py 与 quiz.mts，
#       「页面上有 X 按钮」复用 steps/level_select.py 与 level_select.mts。
#       主页整体形态、切换后文案确实是目标语言、题目内容没被翻译这些语义判断交给 AI。
# 分组：5 条 scenario 互不相干、各自重新打开主页，不标 @scope，各成一个 job。
# 注意：答题页上没有会随语言变化的文案（得分、进度都是数字），「界面变英文」在答题页只能看页面标题、切换按钮与地址栏，
#       这三样都是确定性 step；AI 只判题目内容（汉字与拼音）没被翻译。AI 步没有前后对照的记忆，「生字与选项没变」
#       写成页面级陈述；进度与得分不变由确定性 step 精确判。
#       答对后 1.5 秒才自动切到第 2 题，「进度显示 2 / 10」会等到切题完成再判，之后才点切换按钮。
Feature: 主页与界面语言

  @smoke @engine:midscene
  Scenario: 打开主页
    Given 打开 "http://localhost:8080"
    Then 页面标题是 "识字大挑战 - 二年级上册"
    And 页面上有 "开始挑战" 按钮
    And 语言切换按钮显示 "EN"
    And "当前是主页：显示课件标题「识字大挑战」与开始挑战按钮"

  @regression @engine:novaact
  Scenario: 用地址参数以英文界面启动
    Given 打开 "http://localhost:8080/?lang=en"
    Then 页面标题是 "Character Challenge - Grade 2, Volume 1"
    And 页面上有 "Start Challenge" 按钮
    And 语言切换按钮显示 "中文"
    And "the home page shows the title Character Challenge and a Start Challenge button, both in English"

  @smoke @engine:midscene
  Scenario: 在主页切换语言再切回
    Given 打开 "http://localhost:8080"
    When "点击右上角显示 EN 的语言切换按钮"
    Then 页面标题是 "Character Challenge - Grade 2, Volume 1"
    And 语言切换按钮显示 "中文"
    And 地址栏的 "lang" 参数是 "en"
    And "主页文案已变为英文：课件标题是 Character Challenge，按钮是 Start Challenge"
    When "点击右上角显示「中文」的语言切换按钮"
    Then 页面标题是 "识字大挑战 - 二年级上册"
    And 语言切换按钮显示 "EN"
    And 地址栏的 "lang" 参数是 "zh"
    And "主页文案已变回中文：课件标题是「识字大挑战」，按钮是「开始挑战」"

  @regression @engine:midscene
  Scenario: 答题中途切换语言不丢状态
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "选择第 1 组"
    And 选择当前生字的正确拼音
    Then 得分为 "1"
    And 进度显示 "2 / 10"
    When "点击右上角显示 EN 的语言切换按钮"
    Then 语言切换按钮显示 "中文"
    And 地址栏的 "lang" 参数是 "en"
    And 页面标题是 "Character Challenge - Grade 2, Volume 1"
    And "生字卡上仍是一个汉字，下方仍是四个拼音选项，题目内容没有被翻译成英文"
    And 进度显示 "2 / 10"
    And 得分为 "1"

  @regression @engine:midscene
  Scenario: 切到英文后刷新页面仍是英文界面
    Given 打开 "http://localhost:8080"
    When "点击右上角显示 EN 的语言切换按钮"
    Then 地址栏的 "lang" 参数是 "en"
    When 刷新页面
    Then 页面标题是 "Character Challenge - Grade 2, Volume 1"
    And 语言切换按钮显示 "中文"
    And 地址栏的 "lang" 参数是 "en"
    And "主页文案是英文：课件标题是 Character Challenge，按钮是 Start Challenge"
