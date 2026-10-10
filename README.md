<div id="top">

<!-- HEADER STYLE: COMPACT -->
# HEALTH-ASSESSMENT
<em>Seven days. Real scores. No diagnosis.</em>

<!-- BADGES -->
<!-- local repository, no metadata badges. -->

<em>Built with the tools and technologies:</em>

<img src="https://img.shields.io/badge/JSON-000000.svg?style=default&logo=JSON&logoColor=white" alt="JSON">
<img src="https://img.shields.io/badge/Python-3776AB.svg?style=default&logo=Python&logoColor=white" alt="Python">

<br clear="left"/>

## Table of Contents

- [Table of Contents](#table-of-contents)
- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
    - [Project Index](#project-index)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Usage](#usage)
    - [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Overview



---

## Features

|      | Component       | Details                              |
| :--- | :-------------- | :----------------------------------- |
| ⚙️  | **Architecture**  | <ul><li>单技能（skill）结构，围绕 <code>scripts/score_checkin.py</code> 单一评分入口</li><li>数据流：用户打卡记录 → 本地个人库 → 评分脚本 → 总分（≥7 个不同日期才输出）</li><li>概念层：**薄肌**（蛋白质 / 抗阻 / 超负荷）+ **黄毛**（执行自评分）</li><li>无服务端、无数据库，纯本地文件驱动</li></ul> |
| 🔩 | **Code Quality**  | <ul><li>评分逻辑**唯一来源**：<code>scripts/score_checkin.py</code>，禁止外部手算</li><li>职责单一：脚本只算分，不做诊断、不开药</li><li>输入校验：日期去重计数，< 7 个不同日期不出总分</li></ul> |
| 📄 | **Documentation** | <ul><li>README 明确边界：**不写**财富、加密、买房、婚姻</li><li>记录归属：每人自己的库，互不混用</li><li>评价处理规则：可测量的评价 → 留下并改行为；人身攻击 → 丢掉</li></ul> |
| 🔌 | **Integrations**  | <ul><li>依赖 <code>full-7.json</code> 作为数据/配置载体</li><li>Python 运行时（<code>python</code> / <code>py</code>）</li><li>JSON 读写作为唯一持久化通道</li></ul> |
| 🧩 | **Modularity**    | <ul><li>评分与记录分离：记录在个人库，计算在脚本</li><li>概念模块化：身体（薄肌）与心理（黄毛）两条独立线</li><li>无跨模块耦合，便于单独替换评分规则</li></ul> |
| 🧪 | **Testing**       | <ul><li>以 <code>full-7.json</code> 作为边界用例（7 个不同日期阈值）</li><li>关键断言：< 7 日期 → 无总分</li><li>无独立测试框架，依赖脚本自校验</li></ul> |
| ⚡️  | **Performance**   | <ul><li>纯本地计算，无网络往返</li><li>单文件 JSON 读写，O(n) 日期去重</li><li>轻量：无重型依赖</li></ul> |
| 🛡️ | **Security**      | <ul><li>数据本地化：记录存于**每个人自己的库**</li><li>无诊断 / 无开药，规避医疗合规风险</li><li>无外部上传，隐私面最小</li></ul> |

---

## Project Structure

```sh
└── health-assessment/
    ├── evals
    │   ├── accept.md
    │   └── fixtures
    ├── LICENSE
    ├── prompts
    │   ├── bomi-required.md
    │   ├── custom-standard.md
    │   ├── huangmao-classification.md
    │   └── optional-items.md
    ├── README.md
    ├── scripts
    │   ├── score_checkin.py
    │   ├── test_score.py
    │   └── validate_skill.py
    ├── SKILL.md
    ├── standards
    │   ├── domains.md
    │   ├── literature.md
    │   ├── safety.md
    │   └── scoring.md
    └── workflows
        ├── 00-bind-library.md
        ├── 01-create-profile.md
        ├── 02-checkin.md
        ├── 03-analyze-file.md
        ├── 04-score.md
        ├── 05-read-memory.md
        └── 06-red-flag.md
```

### Project Index

<details open>
	<summary><b><code>C:\USERS\33446\DESKTOP\SHZ自用SKILL\HEALTH-ASSESSMENT/</code></b></summary>
	<!-- __root__ Submodule -->
	<details>
		<summary><b>__root__</b></summary>
		<blockquote>
			<div class='directory-path' style='padding: 8px 0; color: #666;'>
				<code><b>⦿ __root__</b></code>
			<table style='width: 100%; border-collapse: collapse;'>
			<thead>
				<tr style='background-color: #f8f9fa;'>
					<th style='width: 30%; text-align: left; padding: 8px;'>File Name</th>
					<th style='text-align: left; padding: 8px;'>Summary</th>
				</tr>
			</thead>
				<tr style='border-bottom: 1px solid #eee;'>
					<td style='padding: 8px;'><b><a href='https://github.com/songhangze985-eng/health-assessment/blob/rebuild/personal-health/LICENSE'>LICENSE</a></b></td>
					<td style='padding: 8px;'>- Grants legal permission for anyone to use, modify, and distribute the health-assessment project freely, requiring only that the copyright notice and license text remain included<br>- As the repositorys foundational legal layer, it enables open collaboration across all scoring, check-in, and personal development components without restricting commercial or private use.</td>
				</tr>
			</table>
		</blockquote>
	</details>
	<!-- evals Submodule -->
	<details>
		<summary><b>evals</b></summary>
		<blockquote>
			<div class='directory-path' style='padding: 8px 0; color: #666;'>
				<code><b>⦿ evals</b></code>
			<!-- fixtures Submodule -->
			<details>
				<summary><b>fixtures</b></summary>
				<blockquote>
					<div class='directory-path' style='padding: 8px 0; color: #666;'>
						<code><b>⦿ evals.fixtures</b></code>
					<table style='width: 100%; border-collapse: collapse;'>
					<thead>
						<tr style='background-color: #f8f9fa;'>
							<th style='width: 30%; text-align: left; padding: 8px;'>File Name</th>
							<th style='text-align: left; padding: 8px;'>Summary</th>
						</tr>
					</thead>
						<tr style='border-bottom: 1px solid #eee;'>
							<td style='padding: 8px;'><b><a href='https://github.com/songhangze985-eng/health-assessment/blob/rebuild/personal-health/evals/fixtures/full-7.json'>full-7.json</a></b></td>
							<td style='padding: 8px;'>- Provides a complete seven-day check-in fixture for validating the personal development and health assessment skill, covering protein intake, resistance training with overload, execution self-rating, and classification of feedback<br>- It supplies the minimum distinct dates required before any total score appears, ensuring scoring logic is exercised only through the dedicated script and never through diagnosis or unrelated life domains.</td>
						</tr>
					</table>
				</blockquote>
			</details>
		</blockquote>
	</details>
	<!-- scripts Submodule -->
	<details>
		<summary><b>scripts</b></summary>
		<blockquote>
			<div class='directory-path' style='padding: 8px 0; color: #666;'>
				<code><b>⦿ scripts</b></code>
			<table style='width: 100%; border-collapse: collapse;'>
			<thead>
				<tr style='background-color: #f8f9fa;'>
					<th style='width: 30%; text-align: left; padding: 8px;'>File Name</th>
					<th style='text-align: left; padding: 8px;'>Summary</th>
				</tr>
			</thead>
				<tr style='border-bottom: 1px solid #eee;'>
					<td style='padding: 8px;'><b><a href='https://github.com/songhangze985-eng/health-assessment/blob/rebuild/personal-health/scripts/score_checkin.py'>score_checkin.py</a></b></td>
					<td style='padding: 8px;'>Scripts/score_checkin.py` — 摘要## 目的这是「个人发展与健康评估」技能中<strong>唯一的评分权威</strong>。它把用户每日打卡记录转换为确定性的分数与反馈分类，确保模型不会自行重算或臆造分数——模型只能运行此脚本并如实报告其 JSON 输出。## 在整体架构中的角色-<strong>输入层</strong>：读取用户个人档案（身高、体重、年龄、性别、训练年限、伤病）与按日期记录的打卡数据。-<strong>规则层</strong>：依据邵艾伦与孙宇晨长谈中关于身体与心理抗压的原则进行判定：-<strong>身体维度（薄肌）</strong>：围绕蛋白质摄入、抗阻训练、超负荷原则评估。-<strong>心理维度（黄毛）</strong>：执行自评分机制——可测量的评价保留并用于改进行为，人身攻击类内容丢弃。-<strong>输出层</strong>：产出结构化 JSON，包含分数、分类标签与反馈建议。## 关键行为约束-<strong>数据门槛</strong>：记录分散在每个人自己的库中；不满 <strong>7 个不同日期</strong> 不出总分，避免样本不足导致的误导性结论。-<strong>安全边界</strong>：脚本识别红旗信号（如胸痛、晕厥、自伤、自行停药、急性剧痛等），触发时不做常规评分。-<strong>非医疗定位</strong>：不诊断、不开药；不涉及财富、加密、买房、婚姻等话题。-<strong>确定性</strong>：同一输入必得同一输出，杜绝模型自由发挥。## 达成效果该文件将主观的「身心抗压」对话原则固化为可复现的评分流程，使技能在跨用户、跨会话场景下保持一致、可审计、可信任。</td>
				</tr>
				<tr style='border-bottom: 1px solid #eee;'>
					<td style='padding: 8px;'><b><a href='https://github.com/songhangze985-eng/health-assessment/blob/rebuild/personal-health/scripts/test_score.py'>test_score.py</a></b></td>
					<td style='padding: 8px;'>Score_checkin.py 的评分行为是否符合个人发展与健康评估技能规则。通过模拟不同训练与心理记录场景，确认满七天窗口才出总分、缺失必填项不归零、红旗信号停止评分、自定义蛋白目标生效、无效分类降低心理分等边界条件，并生成固定测试数据，保障评分逻辑稳定可靠。</td>
				</tr>
				<tr style='border-bottom: 1px solid #eee;'>
					<td style='padding: 8px;'><b><a href='https://github.com/songhangze985-eng/health-assessment/blob/rebuild/personal-health/scripts/validate_skill.py'>validate_skill.py</a></b></td>
					<td style='padding: 8px;'>Guards the health-assessment skills integrity by confirming every required standard, workflow, prompt, and evaluation asset exists, verifying the skill name and conclusion labels, rejecting forbidden wealth, crypto, housing, and marriage terms, and enforcing a concise SKILL.md, ensuring the codebase stays aligned with its personal development and resilience focus.</td>
				</tr>
			</table>
		</blockquote>
	</details>
</details>

---

## Getting Started

### Prerequisites

This project requires the following dependencies:

- **Programming Language:** Python

### Installation

Build health-assessment from the source and intsall dependencies:

1. **Clone the repository:**

    ```sh
    git clone https://github.com/songhangze985-eng/health-assessment.git
    cd health-assessment
    git checkout rebuild/personal-health
    ```

这个仓库没有第三方安装依赖。调用技能时阅读 `SKILL.md`。计分只运行：

```sh
py -3 scripts/score_checkin.py payload.json
```

### Testing

```sh
py -3 scripts/test_score.py
py -3 scripts/validate_skill.py
```

---

## Roadmap

- [X] **`Task 1`**: <strike>Implement feature one.</strike>
- [ ] **`Task 2`**: Implement feature two.
- [ ] **`Task 3`**: Implement feature three.

---

## Contributing

- **Issues**: https://github.com/songhangze985-eng/health-assessment/issues
- **Pull requests**: https://github.com/songhangze985-eng/health-assessment/pulls

<details closed>
<summary>Contributing Guidelines</summary>

1. **Fork the Repository**: Start by forking https://github.com/songhangze985-eng/health-assessment
2. **Clone Locally**:
   ```sh
   git clone https://github.com/songhangze985-eng/health-assessment.git
   ```
3. **Create a New Branch**: Always work on a new branch, giving it a descriptive name.
   ```sh
   git checkout -b new-feature-x
   ```
4. **Make Your Changes**: Develop and test your changes locally.
5. **Commit Your Changes**: Commit with a clear message describing your updates.
   ```sh
   git commit -m 'Implemented new feature x.'
   ```
6. **Push**: Push the changes to your forked repository.
   ```sh
   git push origin new-feature-x
   ```
7. **Submit a Pull Request**: Create a PR against the original project repository. Clearly describe the changes and their motivations.
8. **Review**: Once your PR is reviewed and approved, it will be merged into the main branch. Congratulations on your contribution!
</details>

<details closed>
<summary>Contributor Graph</summary>
<br>
<p align="left">
   <a href="https://github.com/songhangze985-eng/health-assessment/graphs/contributors">
      <img src="https://contrib.rocks/image?repo=songhangze985-eng/health-assessment">
   </a>
</p>
</details>

---

## License

Health-assessment is protected under the [LICENSE](https://choosealicense.com/licenses) License. For more details, refer to the [LICENSE](https://choosealicense.com/licenses/) file.

---

## Acknowledgments

- Credit `contributors`, `inspiration`, `references`, etc.

<div align="right">

[![][back-to-top]](#top)

</div>


[back-to-top]: https://img.shields.io/badge/-BACK_TO_TOP-151515?style=flat-square


---
