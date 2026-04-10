# QCC Enterprise Query

基于企查查公开接口的企业查询 skill，当前封装了 3 个接口：

- `410 企业工商信息`：查基础工商主体信息，成本更省
- `2001 企业信息核验`：查增强核验字段，信息更完整，但费用更高
- `886 企业模糊搜索`：按简称、电话、地址、人名、产品名、经营范围等线索找企业

## 快速用法

### 1. 首次使用先配置凭证

```bash
python3 scripts/manage_credentials.py --app-key "你的QCC_KEY" --secret-key "你的QCC_SECRET_KEY"
```

查看当前凭证状态：

```bash
python3 scripts/manage_credentials.py
```

凭证会写入 `qcc-enterprise-query/.env`，后续复用。

### 2. 常见查询方式

自动路由查询：

```bash
python3 scripts/run_query.py --company-name "企查查科技股份有限公司" --request "查企业信息"
```

查基础工商信息 `410`：

```bash
python3 scripts/registration_details.py --company-name "企查查科技股份有限公司"
```

查增强核验信息 `2001`：

```bash
python3 scripts/basic_details.py --company-name "企查查科技股份有限公司"
```

按线索模糊搜索 `886`：

```bash
python3 scripts/fuzzy_search.py --search-key "010-62621818"
```

## 路由规则

- 只给企业全称或统一社会信用代码时：
  先让用户选择 `410` 或 `2001`
- 只给简称、电话、地址等线索时：
  先走 `886`
- 只要即将执行 `2001`：
  必须先提示费用更高，并让用户二次确认
- 如果用户直接问 `人员规模 / 参保人数 / 联系方式 / 更多邮箱 / 国标行业 / 企业性质`：
  直接进入 `2001` 的费用确认

## 2001 二次确认

如果已经确认要走 `2001`，需要再次确认后才会正式查询：

```bash
python3 scripts/run_query.py \
  --company-name "企查查科技股份有限公司" \
  --request "确认查询" \
  --detail-api 2001 \
  --confirm-expensive \
  --original-request "查人员规模和参保人数"
```

## 适合怎么问

- `查一下“杭州飞致云信息科技有限公司”的企业信息`
- `查一下“杭州飞致云信息科技有限公司”的人员规模和参保人数`
- `通过电话“010-62621818”找企业`

## 相关文件

- [SKILL.md](./SKILL.md)：skill 规则与对话约定
- [references/api-routing.md](./references/api-routing.md)：接口路由说明
- [references/examples.md](./references/examples.md)：示例输入与期望行为
