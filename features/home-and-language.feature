# 对应需求：docs/product-requirements.md 的 F1、F5
# 对应简报：docs/briefs/home-and-language.md
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
