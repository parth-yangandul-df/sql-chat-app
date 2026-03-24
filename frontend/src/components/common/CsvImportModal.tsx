import { useRef, useState } from 'react';
import {
  Modal,
  Button,
  Group,
  Text,
  Stack,
  Alert,
  Progress,
  Code,
  Anchor,
  List,
} from '@mantine/core';
import { IconUpload, IconDownload, IconAlertCircle, IconCheck } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

export interface CsvColumnSpec {
  key: string;
  label: string;
  required: boolean;
  /** If true, split by '|' and treat as string array */
  array?: boolean;
  /** If true, parse as integer */
  integer?: boolean;
}

interface CsvImportModalProps {
  opened: boolean;
  onClose: () => void;
  title: string;
  /** Column specs that define the expected CSV structure */
  columns: CsvColumnSpec[];
  /** Called once per parsed row; should return a Promise */
  onImportRow: (row: Record<string, unknown>) => Promise<unknown>;
  /** Called when all rows have been processed */
  onComplete: () => void;
  /** Template filename for the sample CSV download */
  templateFilename: string;
}

function parseCsv(text: string): string[][] {
  const lines = text.trim().split(/\r?\n/);
  return lines.map((line) => {
    const result: string[] = [];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuotes && line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (ch === ',' && !inQuotes) {
        result.push(cur.trim());
        cur = '';
      } else {
        cur += ch;
      }
    }
    result.push(cur.trim());
    return result;
  });
}

export function CsvImportModal({
  opened,
  onClose,
  title,
  columns,
  onImportRow,
  onComplete,
  templateFilename,
}: CsvImportModalProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [done, setDone] = useState(false);

  function reset() {
    setErrors([]);
    setProgress(null);
    setDone(false);
    if (fileRef.current) fileRef.current.value = '';
  }

  function handleClose() {
    reset();
    onClose();
  }

  function downloadTemplate() {
    const header = columns.map((c) => c.key).join(',');
    const blob = new Blob([header + '\n'], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = templateFilename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleFile(file: File) {
    reset();
    const text = await file.text();
    const rows = parseCsv(text);
    if (rows.length < 2) {
      setErrors(['CSV must have a header row and at least one data row.']);
      return;
    }

    const header = rows[0].map((h) => h.toLowerCase().trim());
    const dataRows = rows.slice(1).filter((r) => r.some((c) => c !== ''));

    // Validate required columns exist in header
    const missing = columns
      .filter((c) => c.required)
      .filter((c) => !header.includes(c.key.toLowerCase()));
    if (missing.length > 0) {
      setErrors([`Missing required columns: ${missing.map((c) => c.key).join(', ')}`]);
      return;
    }

    const parseErrors: string[] = [];
    const parsed: Record<string, unknown>[] = [];

    dataRows.forEach((row, i) => {
      const rowNum = i + 2; // account for header
      const record: Record<string, unknown> = {};
      let rowValid = true;

      for (const col of columns) {
        const idx = header.indexOf(col.key.toLowerCase());
        const raw = idx >= 0 ? (row[idx] ?? '').trim() : '';

        if (col.required && !raw) {
          parseErrors.push(`Row ${rowNum}: "${col.key}" is required`);
          rowValid = false;
          continue;
        }

        if (col.array) {
          record[col.key] = raw ? raw.split('|').map((s) => s.trim()).filter(Boolean) : [];
        } else if (col.integer) {
          record[col.key] = raw ? parseInt(raw, 10) : 0;
        } else {
          record[col.key] = raw || undefined;
        }
      }

      if (rowValid) parsed.push(record);
    });

    if (parseErrors.length > 0) {
      setErrors(parseErrors);
      return;
    }

    // Import rows sequentially with progress
    setProgress({ done: 0, total: parsed.length });
    const importErrors: string[] = [];

    for (let i = 0; i < parsed.length; i++) {
      try {
        await onImportRow(parsed[i]);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        importErrors.push(`Row ${i + 2}: ${msg}`);
      }
      setProgress({ done: i + 1, total: parsed.length });
    }

    if (importErrors.length > 0) {
      setErrors(importErrors);
    }

    const successCount = parsed.length - importErrors.length;
    notifications.show({
      title: 'CSV import complete',
      message: `${successCount} of ${parsed.length} rows imported successfully`,
      color: importErrors.length > 0 ? 'yellow' : 'green',
      icon: <IconCheck size={16} />,
    });

    setDone(true);
    onComplete();
  }

  const pct = progress ? Math.round((progress.done / progress.total) * 100) : 0;
  const importing = !!progress && !done;

  return (
    <Modal opened={opened} onClose={handleClose} title={title} size="md">
      <Stack gap="md">
        <Group justify="space-between">
          <Text size="sm" c="dimmed">
            Upload a CSV file to bulk-import rows. Use the template for correct column order.
          </Text>
          <Anchor size="sm" onClick={downloadTemplate} style={{ cursor: 'pointer' }}>
            <Group gap={4}>
              <IconDownload size={14} />
              Download template
            </Group>
          </Anchor>
        </Group>

        <Stack gap={4}>
          <Text size="xs" fw={500} c="dimmed">
            Required columns:
          </Text>
          <List size="xs" spacing={2}>
            {columns.map((c) => (
              <List.Item key={c.key}>
                <Code>{c.key}</Code>
                {c.required ? '' : ' (optional)'}
                {c.array ? ' — separate multiple values with |' : ''}
              </List.Item>
            ))}
          </List>
        </Stack>

        {errors.length > 0 && (
          <Alert color="red" icon={<IconAlertCircle size={16} />} title="Import errors">
            <Stack gap={2}>
              {errors.slice(0, 10).map((e, i) => (
                <Text key={i} size="xs">
                  {e}
                </Text>
              ))}
              {errors.length > 10 && (
                <Text size="xs" c="dimmed">
                  …and {errors.length - 10} more
                </Text>
              )}
            </Stack>
          </Alert>
        )}

        {progress && (
          <Stack gap={4}>
            <Progress value={pct} animated={importing} />
            <Text size="xs" c="dimmed" ta="center">
              {progress.done} / {progress.total} rows processed
            </Text>
          </Stack>
        )}

        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />

        <Group justify="flex-end">
          <Button variant="subtle" onClick={handleClose} disabled={importing}>
            {done ? 'Close' : 'Cancel'}
          </Button>
          <Button
            leftSection={<IconUpload size={16} />}
            onClick={() => fileRef.current?.click()}
            disabled={importing}
            loading={importing}
          >
            {importing ? 'Importing…' : 'Choose CSV file'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
