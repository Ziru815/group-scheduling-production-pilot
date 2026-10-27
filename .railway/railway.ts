import { defineRailway, postgres, preserve, project, service } from "railway/iac";

export default defineRailway(() => {
  const database = postgres("postgres");

  const app = service("app", {
    build: {
      builder: "DOCKERFILE",
      dockerfilePath: "Dockerfile",
    },
    deploy: {
      startCommand:
        "sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'",
      preDeployCommand: ["alembic upgrade head"],
      healthcheckPath: "/ready",
      healthcheckTimeout: 300,
      restartPolicyType: "ON_FAILURE",
      restartPolicyMaxRetries: 10,
      region: "asia-southeast1-eqsg3a",
      numReplicas: 1,
    },
    env: {
      APP_ENVIRONMENT: "production",
      DATABASE_URL: database.env.DATABASE_URL,
      AUTO_CREATE_TABLES: "false",
      DEBUG_AUTH_ENABLED: "false",
      USE_MOCK_PROVIDERS: "false",
      SESSION_COOKIE_SECURE: "true",
      APP_SESSION_SECRET: preserve(),
      FRONTEND_BASE_URL: preserve(),
      ALLOWED_ORIGINS: preserve(),
      GOOGLE_CLIENT_ID: preserve(),
      GOOGLE_CLIENT_SECRET: preserve(),
      GOOGLE_REDIRECT_URI: preserve(),
      ONEMAP_TOKEN: preserve(),
    },
  });

  return project("group-scheduling", { resources: [database, app] });
});
