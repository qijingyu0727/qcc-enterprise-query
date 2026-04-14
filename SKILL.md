---
name: qcc-enterprise-query
description: Query enterprise information through QCC public APIs with reusable local credential storage, candidate confirmation, and progressive detail lookup. Use when the user wants QCC/企查查 enterprise lookup, credential setup for the QCC skill, fuzzy company search, or enterprise registration/verification details by company full name or keyword.
---

# QCC Enterprise Query

使用这个 skill 处理企查查公开接口版企业查询。当前支持 3 种能力：

- `1. 企业工商信息`：精确查询企业基础工商主体信息，字段较基础，成本更省。
- `2. 企业信息核验`：精确查询增强版主体核验详情，可补充人员规模、参保人数、国标行业、联系方式、更多邮箱等增强字段，但费用更高。
- `3. 企业模糊搜索`：按企业简称、电话、地址、人名、产品名、经营范围等关键词找候选企业。

## 快速规则

1. 第一次使用时，先检查本地是否已有 `QCC_KEY` 和 `QCC_SECRET_KEY`。
2. 如果没有凭证，不要直接查接口；先向用户索要 `QCC Key` 和 `QCC SecretKey`。
3. 收到凭证后，先调用 `scripts/manage_credentials.py` 写入 `qcc-enterprise-query/.env`，后续复用且不自动删除。
4. 如果用户问“这个 skill 能干嘛”，不要调接口，直接按 3 个接口的能力范围做静态介绍。
5. 如果用户只给了简称、电话、地址、人名、产品名、经营范围等线索，先调用 `scripts/fuzzy_search.py`。
6. `fuzzy_search.py` 返回候选企业后，先让用户确认完整企业全称；确认前不要直接查详情接口。
7. 候选企业列表要带序号；用户回复企业全称，或回复 `2 / 第二个 / 第2个` 这类序号选择时，都视为已经选中目标企业，直接进入下一步，不要再额外追问“是否确认”。
8. 用户确认完整企业全称后，如果原始诉求只是泛查询（如“查企业信息 / 查一下企业 / 查下基本信息”），默认先返回第 `1` 种企业工商信息结果。
9. 如果用户一开始就给了完整企业全称或统一社会信用代码，且诉求是泛查询，也默认直接先查第 `1` 种，不再先做类型选择。
10. 返回第 `1` 种结果后，要继续提示：
   如果还想补人员规模、参保人数、行业、联系方式等信息，可以直接回复 `需要`，但这类继续查询可能会消耗较高费用。
11. 如果用户直接要求 `人员规模 / 参保人数 / 联系方式 / 更多邮箱 / 国标行业 / 企业性质` 等增强字段，则进入第 `2` 种查询的费用确认。
12. 如果用户是在基础结果后回复 `需要`，则直接调用 `scripts/basic_details.py`，不再额外二次确认。
13. 如果用户是一开始就明确要求增强字段，才先提示这类查询费用更高，并做一次确认；用户确认后，再调用 `scripts/basic_details.py`。
14. 用户已明确说“查企业工商信息”时，可直接调用 `scripts/registration_details.py`；用户已明确说“查企业信息核验”时，也先走费用确认，再调用 `scripts/basic_details.py`。
15. 默认推荐并默认执行第 `1` 种；只有诉求明确需要增强字段时，才升级到第 `2` 种。

## 能力介绍话术

当用户问“你能做什么”“这个 skill 能干嘛”时，按下面 3 组能力介绍：

- `1. 企业工商信息`
  适合基础工商信息查询，可返回企业名称、统一社会信用代码、法定代表人、登记状态、成立日期、注册资本、企业类型、所属地区、注册地址、经营范围、营业期限、登记机关、核准日期、上市状态等。
- `2. 企业信息核验`
  适合增强核验查询，在基础主体信息之外，还可补充企业性质、人员规模(PersonScope)、参保人数、国标行业、企查查行业、电话、更多电话、邮箱、更多邮箱、网址、曾用名等。
- `3. 企业模糊搜索`
  适合企业识别和线索定位，可根据企业简称、电话、地址、人名、产品名、经营范围等关键词返回候选企业。

## 路由规则

- 用户未配置凭证：
  先索要 `QCC Key` 和 `QCC SecretKey`，写入 `.env` 后再继续。
- 用户给了不完整企业名称或其他线索：
  调用 `scripts/fuzzy_search.py`。
- `fuzzy_search.py` 返回候选企业后：
  先让用户确认具体企业全称，再继续下一步。
- 用户已给出完整企业全称或统一社会信用代码，且只是泛查询：
  默认直接返回第 `1` 种企业工商信息。
- 用户直接要求增强字段，但还没有明确选第 `2` 种：
  直接返回费用确认提示，确认后执行第 `2` 种查询。
- 用户在基础结果后回复 `需要`：
  直接执行第 `2` 种查询，不再额外确认。
- 用户已经选择/明确指定第 `2` 种：
  再返回费用确认提示，并要求用户回复 `确认` 后再执行。
- 用户已明确选第 `1` 种：
  调用 `scripts/registration_details.py`。
- 用户确认继续执行高价的第 `2` 种查询：
  调用 `scripts/basic_details.py`。
- 详情接口未命中时：
  自动回退 `scripts/fuzzy_search.py`，返回候选企业并让用户重新确认企业全称。

## 输出要求

- 默认返回详细 Markdown 报告。
- 无凭证时，先返回凭证配置提示，不查接口。
- 只有在用户明确要求解释差异时，才返回 `1/2` 差异说明。
- 即将执行第 `2` 种查询时，先返回费用确认提示，不直接查详情。
- 候选企业确认阶段，最多展示前 5 条，优先用表格展示。
- 候选企业表格需要带 `序号` 列，方便用户直接回复“第几个”。
- 默认查“企业信息 / 基本信息 / 工商信息”时：
  直接返回第 `1` 种结果。
- 查 `人员规模 / 参保人数 / 联系方式 / 更多邮箱 / 国标行业 / 企业性质` 等增强字段时：
  直接进入第 `2` 种查询确认。
- 第 `2` 种默认返回完整增强字段报告。
- 第 `1` 种返回基础工商信息报告。
- 如果用户选了第 `1` 种却要查第 `2` 种才有的增强字段，要明确提示可改用第 `2` 种。
- 候选企业确认阶段，只做企业确认，不同时询问查询类型。
- 候选企业确认提示要明确写成：
  `你要查哪一家？直接回企业全称或者第几个就行。`
- 用户回复 `2 / 第二个 / 第2个` 这类序号选择时，直接按对应候选企业进入下一步，不再重复确认企业。
- 基础结果返回后，要明确告诉用户：
  `如果你还想继续补充人员规模、参保人数、行业、联系方式等信息，可以直接回复 需要；继续查询可能会消耗较高费用。`
- 进入第 `2` 种确认阶段时，要明确告诉用户：
  `你选的是企业信息核验。`
  `这个查询费用较高。`
  如确认继续，请回复 `确认`；
  如无需查询参保人数、邮箱电话等信息，可回复 `企业工商信息` 或 `1` 改查基础工商信息。
- 查询完成后的“后续建议”只能提当前 skill 已支持的能力：
  可以建议继续查别的企业，或补充更多支持的增强字段；
  不要提 `股东信息 / 对外投资 / 司法风险 / 历史变更` 等当前未封装能力。

## 本地命令

查看当前凭证状态：

```bash
python3 /Users/qixiaoc/Code/fit2cloud/QCC-skill/qcc-enterprise-query/scripts/manage_credentials.py
```

写入凭证：

```bash
python3 /Users/qixiaoc/Code/fit2cloud/QCC-skill/qcc-enterprise-query/scripts/manage_credentials.py --app-key "你的QCC_KEY" --secret-key "你的QCC_SECRET_KEY"
```

查第 `1` 种企业工商信息：

```bash
python3 /Users/qixiaoc/Code/fit2cloud/QCC-skill/qcc-enterprise-query/scripts/registration_details.py --company-name "企查查科技股份有限公司"
```

查第 `2` 种企业信息核验：

```bash
python3 /Users/qixiaoc/Code/fit2cloud/QCC-skill/qcc-enterprise-query/scripts/basic_details.py --company-name "企查查科技股份有限公司"
```

查企业模糊搜索：

```bash
python3 /Users/qixiaoc/Code/fit2cloud/QCC-skill/qcc-enterprise-query/scripts/fuzzy_search.py --search-key "北京市海淀区东北旺西路8号院"
```

自动路由并生成报告：

```bash
python3 /Users/qixiaoc/Code/fit2cloud/QCC-skill/qcc-enterprise-query/scripts/run_query.py --company-name "企查查科技股份有限公司" --request "查企业信息"
```

确认继续执行第 `2` 种查询：

```bash
python3 /Users/qixiaoc/Code/fit2cloud/QCC-skill/qcc-enterprise-query/scripts/basic_details.py --company-name "企查查科技股份有限公司"
```

## 参考文件

- 路由与参数说明：见 [api-routing.md](./references/api-routing.md)
- 示例请求与期望行为：见 [examples.md](./references/examples.md)
