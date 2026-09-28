# 对应需求：docs/product-requirements.md 的 F3
# 对应简报：docs/briefs/quiz.md
Feature: 答题页

  @smoke @engine:midscene
  Scenario: 进入第 1 组显示第 1 题
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "选择第 1 组"
    Then "生字卡上显示的是一个汉字"
    And 拼音选项有 "4" 个
    And 进度显示 "1 / 10"
    And 得分为 "0"

  @smoke @engine:midscene
  Scenario: 答对加一分并自动进入下一题
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "选择第 1 组"
    And 选择当前生字的正确拼音
    Then "被选中的拼音选项呈绿色的答对状态"
    And 得分为 "1"
    And 作答后 "1.5" 秒自动进入第 "2" 题

  @regression @engine:midscene
  Scenario: 答错不加分并高亮正确答案
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "选择第 1 组"
    And 选择一个错误的拼音
    Then "被选中的拼音选项呈红色的答错状态，另有一个选项以绿色高亮出正确答案"
    And 得分为 "0"
    And 作答后 "3" 秒自动进入第 "2" 题

  @regression @engine:midscene
  Scenario: 一题只答一次
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "选择第 1 组"
    And 选择当前生字的正确拼音
    And 再点一个尚未高亮的拼音选项
    Then 得分为 "1"
    And 处于答对状态的选项有 "1" 个，处于答错状态的选项有 "0" 个

  @regression @engine:novaact
  Scenario: 英文界面下答对加一分
    Given 打开 "http://localhost:8080/?lang=en"
    When "click the Start Challenge button"
    Then "the level selection page shows its heading, level buttons and back button in English"
    When "choose Group 1"
    And 选择当前生字的正确拼音
    Then "the selected pinyin option is highlighted green as correct"
    And 得分为 "1"
    And 作答后 "1.5" 秒自动进入第 "2" 题
