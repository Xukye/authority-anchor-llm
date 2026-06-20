# 主轴 30 案 · 温度档 Roadmap

> 命名 `模型_臂_温度`:臂 N=非思考 / T=思考。温度档对照论文 **Table 8(温度档表)**。
> 角色:**主**=T=0 同温主对比(0/0);**稳定性**=换温重跑的稳健性检验;**厂锁**=厂商固定温度、无 T=0 基线。

| 模型 | 文件 | 臂 | 温度 | 角色 | 条数 |
|---|---|---|---|---|---|
| Gemini | `Gemini_N_0.json` | 非思考 | 0 | 主 | 390 |
| Gemini | `Gemini_N_0.7.json` | 非思考 | 0.7 | 稳定性 | 1170 |
| Gemini | `Gemini_T_0.json` | 思考 | 0 | 主 | 390 |
| Gemini | `Gemini_T_0.7.json` | 思考 | 0.7 | 稳定性 | 1170 |
| GLM | `GLM_N_0.json` | 非思考 | 0 | 主 | 390 |
| GLM | `GLM_N_0.7.json` | 非思考 | 0.7 | 稳定性 | 1170 |
| GLM | `GLM_T_0.json` | 思考 | 0 | 主 | 393 |
| MiMo | `MiMo_N_0.json` | 非思考 | 0 | 主 | 399 |
| MiMo | `MiMo_N_0.7.json` | 非思考 | 0.7 | 稳定性 | 1170 |
| MiMo | `MiMo_T_0.json` | 思考 | 0 | 主 | 390 |
| MiMo | `MiMo_T_0.7.json` | 思考 | 0.7 | 稳定性 | 1170 |
| Grok | `Grok_N_0.json` | 非思考 | 0 | 主 | 390 |
| Grok | `Grok_N_0.7.json` | 非思考 | 0.7 | 稳定性 | 1170 |
| Grok | `Grok_T_0.json` | 思考 | 0 | 主 | 390 |
| Grok | `Grok_T_0.7.json` | 思考 | 0.7 | 稳定性 | 1170 |
| Doubao | `Doubao_N_1.0.json` | 非思考 | 1.0 | 主·厂锁 | 390 |
| Doubao | `Doubao_T_1.0.json` | 思考 | 1.0 | 主·厂锁 | 390 |
| DeepSeek | `DeepSeek_N_0.json` | 非思考 | 0 | 主 | 390 |
| DeepSeek | `DeepSeek_N_0.7.json` | 非思考 | 0.7 | 稳定性 | 1170 |
| DeepSeek | `DeepSeek_T_0.7.json` | 思考 | 0.7 | 稳定性·厂锁 | 1170 |
| Kimi | `Kimi_N_0.6.json` | 非思考 | 0.6 | 稳定性·厂锁 | 1170 |
| Kimi | `Kimi_T_1.0.json` | 思考 | 1.0 | 稳定性·厂锁 | 1278 |

**注:**
- Gemini/GLM/MiMo/Grok:主对比 T=0/0(干净);并各跑 0.7 稳定性(GLM 思考 0.7 未跑,仅非思考)。
- Doubao:思考/非思考均厂锁 1.0,无 T=0 臂。
- DeepSeek:**非思考不锁(0,主)、思考厂锁 0.7**;稳定性把非思考也移到 0.7。
- Kimi:**非思考锁 0.6、思考锁 1.0**(无 T=0,故不在主 T=0 组,需另套 kimi_override 语义修正)。
- 校正(parse_corrections 21 条)已并入各文件 `parsed_amount`。