import { describe, expect, it } from 'vitest';
import {
  keeperFieldDefinition,
  keeperOperatorOptions,
  keeperPreset,
  keeperRuleFields,
} from './duplicateKeeperRules';

describe('duplicate keeper rules', () => {
  it('uses one Date field for newest and oldest preferences', () => {
    let id = 1;
    const nextId = () => id++;
    const newest = keeperPreset('Prefer newest', nextId);
    const oldest = keeperPreset('Prefer oldest', nextId);
    expect(newest.find((rule) => rule.field === 'date')?.operator).toBe('highest');
    expect(oldest.find((rule) => rule.field === 'date')?.operator).toBe('lowest');
    expect(keeperRuleFields.map((field) => String(field.value))).not.toContain('newest');
    expect(keeperRuleFields.map((field) => String(field.value))).not.toContain('oldest');
  });

  it('exposes the rapid metadata and source fields', () => {
    const fields = new Set(keeperRuleFields.map((field) => field.value));
    for (const field of ['library', 'folder', 'filename', 'mime_type', 'file_size', 'resolution', 'favorite', 'edited', 'tag', 'album', 'reference', 'similarity', 'metadata_richness', 'format_quality'] as const) {
      expect(fields.has(field)).toBe(true);
    }
  });

  it('labels raw link depth as hops from reference', () => {
    expect(keeperFieldDefinition('link_depth').label).toBe('Hops from reference');
  });

  it('keeps ranking operators out of hard requirements', () => {
    const definition = keeperFieldDefinition('file_size');
    const requireOperators = keeperOperatorOptions(definition.value, 'require').map((option) => option.value);
    const preferOperators = keeperOperatorOptions(definition.value, 'prefer').map((option) => option.value);
    expect(requireOperators).not.toContain('highest');
    expect(preferOperators).toContain('highest');
    expect(preferOperators).toContain('lowest');
  });

  it('highest-quality preset requires online assets before ranking quality', () => {
    let id = 1;
    const rules = keeperPreset('Highest quality', () => id++);
    expect(rules[0]).toMatchObject({ effect: 'require', field: 'availability', value: 'online' });
    expect(rules.some((rule) => rule.field === 'resolution' && rule.operator === 'highest')).toBe(true);
    expect(rules.some((rule) => rule.field === 'format_quality' && rule.operator === 'highest')).toBe(true);
  });
});
