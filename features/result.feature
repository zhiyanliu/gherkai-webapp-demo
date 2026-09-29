# 对应需求：docs/product-requirements.md 的 F4（题库见附录 A）
# 对应简报：docs/briefs/result.md
Feature: 结算页

  @smoke @scope:result-replay-and-home @engine:midscene @timeout:600
  Scenario: 全部答对
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "点击第 1 组"
    And 依次答对全部 "10" 题
    Then 结算页的标题是 "挑战完成！"
    And 结算页的最终得分是 "10"
    And 结算页的评语是 "太厉害了！全对！🌟"
    And 页面上有 "再玩一次" 按钮
    And 页面上有 "返回主页" 按钮
    And "结算页整体是一张结算卡：有最终得分、一句评语，以及再玩一次与返回主页两个按钮"

  @regression @engine:midscene
  Scenario: 全部答错
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "点击第 1 组"
    And 依次答错全部 "10" 题
    Then 结算页的标题是 "挑战完成！"
    And 结算页的最终得分是 "0"
    And 结算页的评语是 "再接再厉哦！💪"

  @regression @engine:midscene
  Scenario: 答对 8 题答错 2 题得中间档评语
    Given 打开 "http://localhost:8080"
    When "点击开始挑战按钮"
    And "点击第 1 组"
    And 依次答对 "8" 题，再答错 "2" 题
    Then 结算页的标题是 "挑战完成！"
    And 结算页的最终得分是 "8"
    And 结算页的评语是 "真棒！继续加油！✨"

  @smoke @scope:result-replay-and-home @engine:midscene @timeout:600
  Scenario: 再玩一次回到第 1 题且得分清零
    Given 结算页的最终得分是 "10"
    When "点击再玩一次按钮"
    Then 进度显示 "1 / 10"
    And 得分为 "0"
    And "当前是答题页：生字卡上显示一个汉字，下方是拼音选项"

  @smoke @scope:result-replay-and-home @engine:midscene @timeout:600
  Scenario: 从结算页返回主页
    Given 进度显示 "1 / 10"
    When 依次答对全部 "10" 题
    Then 结算页的标题是 "挑战完成！"
    When "点击返回主页按钮"
    Then 页面上有 "开始挑战" 按钮
    And "当前是主页：显示课件标题「识字大挑战」与开始挑战按钮"

  @regression @engine:novaact
  Scenario: 英文界面下全部答对
    Given 打开 "http://localhost:8080/?lang=en"
    When "click the Start Challenge button"
    And "choose Group 1"
    And 依次答对全部 "10" 题
    Then 结算页的标题是 "Challenge Complete!"
    And 结算页的最终得分是 "10"
    And 结算页的评语是 "Amazing! All correct! 🌟"
    And 页面上有 "Play Again" 按钮
    And 页面上有 "Back to Home" 按钮
    And "the result page shows its heading, the score message and both buttons in English"
