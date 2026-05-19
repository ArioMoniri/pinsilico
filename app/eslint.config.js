// Flat config for the React/TS frontend.
// Python and Rust are linted by their own tooling (ruff, clippy).
// Lives under app/ so the import of `globals` resolves through app/'s
// node_modules without needing a root-level package.json.
//
// Phase 0 keeps the lint baseline simple (recommended + react-hooks).
// Phase 7 (frontend skeleton) re-introduces typed linting once there is
// real frontend code that benefits from the type-aware rules.

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import prettier from "eslint-config-prettier";
import globals from "globals";

export default tseslint.config(
  {
    ignores: [
      "node_modules/**",
      "dist/**",
      ".vite/**",
      "src-tauri/**",
      "coverage/**",
      "playwright-report/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tseslint.parser,
      ecmaVersion: 2022,
      sourceType: "module",
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
    // Three.js / R3F components expose three-specific JSX props (roughness,
    // metalness, position, etc.) that the React plugin doesn't know about.
    // Scoped override keeps the rule active for plain HTML.
    files: ["src/components/scene/**/*.{ts,tsx}"],
    rules: {
      "react/no-unknown-property": "off",
    },
  },
  prettier,
);
