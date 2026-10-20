## 代码结构

```
backend/     FastAPI 后端(见 backend/README.md)
  app/schemas/ir.py    IR 数据模型 —— AI 的唯一输出契约
  app/llm/router.py    ModelRouter —— 模型调用的唯一入口
  app/api/deps.py      角色鉴权(后端强制)
  config/models.yaml   模型配置
  env.yaml.example     本地配置模板(复制为 env.yaml,已忽略)
  tests/               14 个 IR 校验测试
frontend/    Next.js 前端(create-next-app 生成)
  app/                 路由与页面
.venv/       本地 Python 3.12 环境(git 已忽略)
```

- 仓库工作规则:[../AGENTS.md](../AGENTS.md)
