# QCC OpenAPI Routing

当前 skill 使用 3 种企查查公开接口能力：

| 接口 | 地址 | 主参数 | 适用场景 |
| --- | --- | --- | --- |
| `410 企业工商信息` | `https://api.qichacha.com/ECIV4/GetBasicDetailsByName` | `keyword` | 已知企业全称或统一社会信用代码，查基础工商主体信息，成本更省 |
| `2001 企业信息核验` | `https://api.qichacha.com/EnterpriseInfo/Verify` | `searchKey` | 已知企业全称或统一社会信用代码，查增强版主体核验详情，费用更高 |
| `886 企业模糊搜索` | `https://api.qichacha.com/FuzzySearch/GetList` | `searchKey` | 只知道企业简称、电话、地址、人名、产品名、经营范围等线索 |

## 鉴权

- Query 中始终带 `key=QCC_KEY`
- HTTP Header 必带：
  - `Token`
  - `Timespan`
- `Timespan` 为精确到秒的 Unix 时间戳
- `Token = MD5(QCC_KEY + Timespan + QCC_SECRET_KEY)` 的 32 位大写字符串

## 凭证策略

1. 凭证读取顺序固定为：
   `显式传参 > 进程环境变量 > qcc-enterprise-query/.env`
2. 如果本地还没有可用凭证：
   不调任何 QCC 接口，先向用户索要 `QCC Key` 和 `QCC SecretKey`
3. 收到后先写入：
   `qcc-enterprise-query/.env`
4. `.env` 中其他无关变量保留，不自动清理凭证

## 路由顺序

1. 用户问能力说明：
   不调接口，直接静态介绍 3 种能力
2. 用户未配置凭证：
   先返回凭证配置提示
3. 用户只给了简称、电话、地址、人名、产品名、经营范围等线索：
   先走 `886`
4. `886` 返回候选企业：
   先让用户确认完整企业全称；候选列表需带序号，支持用户直接回复企业全称或第几个
5. 用户确认完整企业全称后：
   再让用户选择 `1` 或 `2`
6. 用户一开始就给了完整企业全称或统一社会信用代码：
   也先让用户选择 `1` 或 `2`
7. 用户直接要求增强字段，但尚未明确选第 `2` 种：
   仍先返回 `detail_api_selection`，说明 `1/2` 的区别并推荐第 `2` 种
8. 用户已经选择/明确指定第 `2` 种：
   再返回 `expensive_confirmation`，提示该查询费用更高并等待确认
9. 用户明确选第 `1` 种：
   调 `registration_details.py`
10. 用户确认继续执行高价的第 `2` 种查询：
   调 `basic_details.py`
11. 详情接口未命中：
   自动回退 `886` 重新找候选企业

## 输出约定

- 默认返回 Markdown 报告
- 用户明确要求 JSON 时，返回结构化 JSON
- 无凭证时，返回 `credential_required`
- 需要用户先选详情接口时，返回 `detail_api_selection`
- 需要用户确认高价的第 `2` 种查询时，返回 `expensive_confirmation`
- 候选企业确认阶段，返回 `clarification`
- `clarification` 文案需要明确提示：`你要查哪一家？直接回企业全称或者第几个就行。`
- `expensive_confirmation` 文案需要明确提示：
  `你选的是企业信息核验。`
  `这个查询费用较高。`
  `如果确认继续，请直接回复 确认。`
  `如果无需查询参保人数、邮箱电话等信息，可以选择基础工商信息，回复 企业工商信息 或 1即可。`
- 第 `1` 种默认适合基础工商信息
- 第 `2` 种默认适合增强核验字段
- `detail_api_selection` 需要明确区分：
  第 `1` 种包含哪些基础工商字段；
  第 `2` 种比第 `1` 种额外多出哪些增强字段
- 用户请求增强字段但选择第 `1` 种时，要明确提示可改用第 `2` 种
- 查询后的“后续建议”不能超出当前 skill 能力边界
