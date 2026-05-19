// Flat config — root-level. Lints the React/TS frontend under app/.
// Python and Rust are linted by their own tooling (ruff, clippy).

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import prettier from "eslint-config-prettier";
import globals from "globals";

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.vite/**",
      "**/src-tauri/target/**",
      "**/src-tauri/gen/**",
      "**/coverage/**",
      "**/playwright-report/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  {
    files: ["app/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        project: ["./app/tsconfig.json"],
        tsconfigRootDir: import.meta.dirname,
      },
      globals: {
        ...globals.browser,
      },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
    },
    settings: {
      react: { version: "18.3" },
    },
    rules: {
      ...react.configs.recommended.rules,
      ...react.configs["jsx-runtime"].rules,
      ...reactHooks.configs.recommended.rules,
      "react/prop-types": "off",
      // BUILD_PROMPT.md §5: zero unexplained `@ts-ignore`. Force a comment.
      "@typescript-eslint/ban-ts-comment": [
        "error",
        {
          "ts-expect-error": "allow-with-description",
          "ts-ignore": true,
          "ts-nocheck": true,
          minimumDescriptionLength: 10,
        },
      ],
    },
  },
  {
    files: ["app/**/*.config.{ts,js}", "app/vite.config.ts", "app/vitest.config.ts"],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
  prettier,
);
