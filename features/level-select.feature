# 选关页（需求 F2）。对应简报 docs/briefs/level-select.md，需求 docs/product-requirements.md 第 5 节 F2 与第 4 节题库。
#
# 引擎：界面中文为主，中文场景标 @engine:midscene；英文界面那条标 @engine:novaact，其 AI 步用英文写（Nova Act 面向英文）。
# 分工：选关页标题、关卡按钮个数、每个按钮的两行文案、「返回主页」与「开始挑战」按钮的存在、进入关卡后的进度与得分
#       走确定性 step（steps/level_select.py 与 steps/level_select.mts，进度与得分复用 steps/quiz.py 与 steps/quiz.mts，
#       两引擎成对）；「整体呈现为可点选的关卡列表」「回到主页后是主页形态」「进入了答题页」「英文界面文案确实是英文」
#       这些页面形态与语义判断交给 AI。
# 分组：4 条 scenario 互不相干、各自从主页打开，不标 @scope，各成一个 job。
# 注意：关卡按钮文案里的字母 N 是序号占位：「第 N 组」表示第 1 个按钮是「第 1 组」、第 2 个是「第 2 组」……
#       每组的生字每次打开都随机重分（需求 F2），所以不检查某一组里有哪些字。
Feature: 选关页

  @smoke @engine:midscene
  Scenario: 从主页进入选关页
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    Then 选关页的标题是 "选择关卡"
    And 关卡按钮有 "8" 个
    And 关卡按钮依次标注 "第 N 组" 与 "10 个生字"
    And 页面上有 "返回主页" 按钮
    And "选关页整体呈现为一组可以点选的关卡按钮列表"

  @regression @engine:midscene
  Scenario: 从选关页返回主页
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "点击返回主页按钮"
    Then 页面上有 "开始挑战" 按钮
    And "当前是主页：显示课件标题「识字大挑战」与开始挑战按钮"

  @regression @engine:midscene
  Scenario: 选择第 3 组进入答题页
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "选择第 3 组"
    Then "当前是答题页：生字卡上显示一个汉字，下方是拼音选项"
    And 进度显示 "1 / 10"
    And 得分为 "0"

  @regression @engine:novaact
  Scenario: 英文界面下的选关页
    Given 打开 "http://localhost:8080/?lang=en"
    When "click the Start Challenge button"
    Then 选关页的标题是 "Choose a Level"
    And 关卡按钮有 "8" 个
    And 关卡按钮依次标注 "Group N" 与 "10 characters"
    And 页面上有 "Back to Home" 按钮
    And "the heading, the level buttons and the back button on the level selection page are all in English"
