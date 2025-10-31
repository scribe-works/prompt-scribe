### 2. Важные улучшения

Эти изменения существенно улучшат гибкость и удобство использования инструмента.

#### 2.1. Гибкость `include` и чтение файлов внутри `content`

Текущая реализация `simple assembly` слишком жесткая и неинтуитивная.

**Проблема:**
1.  Директива `include` ожидает **имя переменной**, а не путь к файлу. Как вы заметили, `include: includes/file.md` не работает, потому что код пытается найти переменную с ключом `"includes/file.md"` в словаре `variables`. Это не соответствует ожиданиям пользователя.
2.  В блоке `content` нет механизма для встраивания содержимого файла, что заставляет пользователей либо переходить на более сложный Jinja2, либо создавать множество мелких переменных.

**Предлагаемое решение (убивает двух зайцев):**

Ввести более явный и мощный механизм для работы с файлами, который будет работать как для `include`, так и для подстановок внутри `content`. Предлагаю внедрить специальный префикс для строковых значений в `variables`, например `file:`.

**Шаг 1: Улучшить `_resolve_variables` для поддержки `file:` префикса.**

Мы можем научить `_resolve_variables` автоматически загружать контент файла, если значение переменной начинается с `file:`.

```python
# F:/Projects/prompt-scribe/src/promptscribe/composer.py

# ... внутри класса PromptComposer ...

    def _resolve_variables(self, agent_name: str) -> Dict[str, Any]:
        """
        Resolves and merges global and agent-specific variables.
        It also loads file content for variables with the 'file:' prefix.

        Args:
            agent_name: The name of the agent.

        Returns:
            A dictionary of resolved variables.
        """
        agent_config = self.config.get("agents", {}).get(agent_name, {})
        global_vars = self.config.get("variables", {}).copy()
        agent_vars = agent_config.get("variables", {}).copy()

        merged_vars = {**global_vars, **agent_vars}

        # НОВЫЙ БЛОК: Обработка 'file:' префикса
        resolved_vars = {}
        for key, value in merged_vars.items():
            if isinstance(value, str) and value.startswith("file:"):
                file_path = value[5:].strip()
                # Передаем agent_name для отслеживания зависимостей
                resolved_vars[key] = self._read_file_content(file_path, agent_name)
            else:
                resolved_vars[key] = value

        return resolved_vars
```

**Шаг 2: Упростить и сделать `_run_simple_assembly` более интуитивным.**

Теперь `include` сможет работать и с переменными (как раньше), и с прямыми путями.

```python
# F:/Projects/prompt-scribe/src/promptscribe/composer.py

# ... внутри _run_simple_assembly ...

            if key == 'include':
                # 'value' теперь может быть прямым путем к файлу
                file_content = self._read_file_content(str(value), agent_name)

                if substitute_in_includes:
                    substituted_content = self._substitute_variables(file_content, variables)
                    parts.append(substituted_content)
                else:
                    parts.append(file_content)

            elif key == 'include_raw':
                # Аналогично для include_raw
                file_content = self._read_file_content(str(value), agent_name)
                parts.append(file_content) # Append raw content
# ...
```
*Примечание: в `_run_simple_assembly` старый код с `variables.get(str(value))` нужно полностью заменить на новый, как показано выше, чтобы избежать двойной логики.*

**Как это решит ваши проблемы:**

1.  **Проблема с `include`:** Теперь вы можете писать интуитивно.
    ```yaml
    assembly:
      - include: includes/development-rules.md # Теперь это будет работать!
    ```

2.  **Проблема с `content`:** Вы можете определить переменную с файлом и использовать ее где угодно.
    ```yaml
    variables:
      rules_doc: "file:includes/development-rules.md" # Используем новый префикс

    agents:
      reviewer:
        assembly:
          - content: "Please review the code based on these rules: ${rules_doc}"
    ```

Это решение соответствует принципу **"Predictability over 'Magic'"**, так как префикс `file:` явно указывает на намерение.

#### 2.2. Глобальная переменная для имени агента

Это превосходная идея, полностью соответствующая принципу DRY (Don't Repeat Yourself).

**Проблема:**
Часто `output_file` следует шаблону, включающему имя агента. Это приводит к дублированию в конфигурации.

**Предлагаемое решение:**
Внедрить зарезервированную переменную, которая будет автоматически добавляться в контекст каждого агента.

**Реализация:**
Это очень простое изменение в `compose_agent`.

```python
# F:/Projects/prompt-scribe/src/promptscribe/composer.py

# ... внутри compose_agent ...
        # 1. Resolve variables
        variables = self._resolve_variables(agent_name)
        
        # НОВОЕ: Добавляем зарезервированную переменную с именем агента
        # Используем префикс, чтобы избежать конфликтов с пользовательскими переменными
        variables['_agent_name'] = agent_name

        final_prompt = ""
# ...
```

**Как это использовать:**
Теперь вы можете определить шаблон `output_file` глобально.

```yaml
# prompts.yml
settings:
  output_dir: "composed_prompts"
  # Глобальный шаблон имени файла!
  output_file: "${_agent_name}_${project}.md"

variables:
  project: "prompt_scribe"

agents:
  code-reviewer:
    # output_file больше не нужен, он будет унаследован и сгенерирован
    variables:
      persone: "personas/CODE_REVIEWER.md"
  architect:
    # И здесь тоже не нужен
```
Это делает конфигурацию значительно чище и проще в поддержке. 