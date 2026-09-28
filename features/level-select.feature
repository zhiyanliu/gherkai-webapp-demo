# 对应需求：docs/product-requirements.md 的 F2
# 对应简报：docs/briefs/level-select.md
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
