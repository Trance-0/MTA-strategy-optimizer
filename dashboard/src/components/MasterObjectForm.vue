<script setup>
/**
 * The Form editor: one row per field, instead of a raw JSON object.
 *
 * A field with a closed or suggested vocabulary (provider, availability,
 * ad product, ...) gets a text input backed by a `<datalist>`, which is a
 * search-as-you-type dropdown a non-technical reader already knows from
 * address forms and country pickers, and still accepts a typed value the
 * list does not carry. A field with no vocabulary gets a plain input.
 */
import { computed } from "vue";

import { SECTION_FIELDS } from "../lib/masterObjectFields.js";

const props = defineProps({
  sectionKey: { type: String, required: true },
  modelValue: { type: Object, required: true },
});
const emit = defineEmits(["update:modelValue"]);

const fields = computed(() => SECTION_FIELDS[props.sectionKey] ?? []);

function optionsFor(field) {
  if (field.optionsFor) return field.optionsFor(props.modelValue);
  return field.options ?? [];
}

function listId(field) {
  return `master-object-options-${props.sectionKey}-${field.key}`;
}

function setField(key, value) {
  emit("update:modelValue", { ...props.modelValue, [key]: value });
}

function onTextInput(field, event) {
  setField(field.key, event.target.value);
}

function onNumberInput(field, event) {
  const raw = event.target.value;
  setField(field.key, raw === "" ? null : Number(raw));
}

function onBooleanChange(field, event) {
  const raw = event.target.value;
  setField(field.key, raw === "" ? null : raw === "true");
}

function boolToOption(value) {
  if (value === true) return "true";
  if (value === false) return "false";
  return "";
}

function addToList(field, event) {
  const value = event.target.value.trim();
  event.target.value = "";
  if (!value) return;
  const current = Array.isArray(props.modelValue[field.key]) ? props.modelValue[field.key] : [];
  if (current.includes(value)) return;
  setField(field.key, [...current, value]);
}

function removeFromList(field, value) {
  const current = Array.isArray(props.modelValue[field.key]) ? props.modelValue[field.key] : [];
  setField(field.key, current.filter((item) => item !== value));
}
</script>

<template>
  <div class="master-object-form">
    <div v-for="field in fields" :key="field.key" class="form-row">
      <label :for="`master-object-field-${field.key}`">
        {{ field.label }}<span v-if="field.required" class="required-mark">*</span>
      </label>

      <input
        v-if="field.kind === 'text'"
        :id="`master-object-field-${field.key}`"
        type="text"
        :value="modelValue[field.key] ?? ''"
        @input="onTextInput(field, $event)"
      />

      <input
        v-else-if="field.kind === 'number'"
        :id="`master-object-field-${field.key}`"
        type="number"
        step="any"
        :value="modelValue[field.key] ?? ''"
        @input="onNumberInput(field, $event)"
      />

      <select
        v-else-if="field.kind === 'boolean'"
        :id="`master-object-field-${field.key}`"
        :value="boolToOption(modelValue[field.key])"
        @change="onBooleanChange(field, $event)"
      >
        <option value="">Unknown</option>
        <option value="true">{{ field.trueLabel }}</option>
        <option value="false">{{ field.falseLabel }}</option>
      </select>

      <input
        v-else-if="field.kind === 'select'"
        :id="`master-object-field-${field.key}`"
        type="text"
        :list="listId(field)"
        :value="modelValue[field.key] ?? ''"
        placeholder="Type to search…"
        @input="onTextInput(field, $event)"
      />
      <datalist v-if="field.kind === 'select'" :id="listId(field)">
        <option v-for="option in optionsFor(field)" :key="option" :value="option" />
      </datalist>

      <div v-else-if="field.kind === 'multiselect'" class="form-multiselect">
        <div v-if="(modelValue[field.key] ?? []).length" class="chip-list">
          <span v-for="value in modelValue[field.key]" :key="value" class="chip">
            {{ value }}
            <button
              type="button"
              class="chip-remove"
              :aria-label="`Remove ${value}`"
              @click="removeFromList(field, value)"
            >
              ×
            </button>
          </span>
        </div>
        <input
          :id="`master-object-field-${field.key}`"
          type="text"
          :list="listId(field)"
          :placeholder="`Add ${field.label.toLowerCase()}…`"
          @change="addToList(field, $event)"
        />
        <datalist :id="listId(field)">
          <option v-for="option in optionsFor(field)" :key="option" :value="option" />
        </datalist>
      </div>
    </div>
  </div>
</template>
