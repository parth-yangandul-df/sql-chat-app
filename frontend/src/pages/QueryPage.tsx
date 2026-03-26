import { useState } from 'react';
import {
  Stack,
  Title,
  Textarea,
  Button,
  Group,
  Select,
  Paper,
  Text,
  Table,
  Badge,
  Alert,
  Loader,
  Code,
  Accordion,
  CopyButton,
  ActionIcon,
  Tooltip,
} from '@mantine/core';
import { IconSend, IconCopy, IconCheck, IconAlertCircle } from '@tabler/icons-react';
import { useMutation } from '@tanstack/react-query';
import { queryApi } from '../api/queryApi';
import { useConnections } from '../hooks/useConnections';
import { usePagination } from '../hooks/usePagination';
import { TablePagination } from '../components/common/TablePagination';
import type { QueryResult } from '../types/api';

export function QueryPage() {
  const [question, setQuestion] = useState('');
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);

  const { data: connections, isLoading: loadingConns } = useConnections();

  const queryMutation = useMutation({
    mutationFn: () =>
      queryApi.execute({ connection_id: connectionId!, question }),
    onSuccess: (data) => {
      setResult(data);
    },
  });

  const connOptions =
    connections?.map((c) => ({ value: c.id, label: c.name })) ?? [];

  // Auto-select first connection
  if (!connectionId && connOptions.length > 0) {
    setConnectionId(connOptions[0].value);
  }

  const handleRunQuery = () => {
    setResult(null);
    queryMutation.mutate();
  };

  return (
    <Stack gap="md">
      <Title order={2}>Ask a Question</Title>

      <Group align="flex-end">
        <Select
          label="Database connection"
          placeholder="Select connection..."
          data={connOptions}
          value={connectionId}
          onChange={setConnectionId}
          disabled={loadingConns}
          w={300}
        />
      </Group>

      <Textarea
        placeholder="e.g. Show active resources"
        autosize
        minRows={2}
        maxRows={6}
        value={question}
        onChange={(e) => setQuestion(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            if (connectionId && question.trim()) handleRunQuery();
          }
        }}
      />

      <Group>
        <Button
          leftSection={<IconSend size={16} />}
          onClick={handleRunQuery}
          loading={queryMutation.isPending}
          disabled={!connectionId || !question.trim()}
        >
          Run Query
        </Button>
      </Group>

      {queryMutation.isError && (
        <Alert
          color="red"
          icon={<IconAlertCircle size={16} />}
          title="Query failed"
        >
          {(queryMutation.error as Error).message}
        </Alert>
      )}

      {queryMutation.isPending && (
        <Group justify="center" py="xl">
          <Loader size="lg" />
          <Text>Running query...</Text>
        </Group>
      )}

      {result && <QueryResultView result={result} />}
    </Stack>
  );
}

function QueryResultView({ result }: { result: QueryResult }) {
  const { page, setPage, totalPages, total, paged, pageSize } = usePagination(result.rows);

  return (
    <Stack gap="md">
      {result.summary && (
        <Paper withBorder p="md" bg="blue.0">
          <Text fw={600} mb="xs">
            Summary
          </Text>
          <Text>{result.summary}</Text>
          {result.highlights.length > 0 && (
            <Group mt="xs" gap="xs">
              {result.highlights.map((h, i) => (
                <Badge key={i} variant="light">
                  {h}
                </Badge>
              ))}
            </Group>
          )}
        </Paper>
      )}

      <Accordion variant="contained">
        <Accordion.Item value="sql">
          <Accordion.Control>
            <Group>
              <Text fw={500}>SQL</Text>
              <Badge size="sm" variant="light">
                {result.execution_time_ms}ms
              </Badge>
              <Badge size="sm" variant="light" color="gray">
                {result.row_count} rows
              </Badge>
              {result.retry_count > 0 && (
                <Badge size="sm" color="yellow">
                  {result.retry_count} retries
                </Badge>
              )}
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Group justify="flex-end" mb="xs">
              <CopyButton value={result.final_sql}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? 'Copied' : 'Copy'}>
                    <ActionIcon variant="subtle" onClick={copy}>
                      {copied ? (
                        <IconCheck size={16} />
                      ) : (
                        <IconCopy size={16} />
                      )}
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
            </Group>
            <Code block>{result.final_sql}</Code>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      {result.rows.length > 0 && (
        <Paper withBorder p="sm">
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                {result.columns.map((col) => (
                  <Table.Th key={col}>{col}</Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {paged.map((row, i) => (
                <Table.Tr key={i}>
                  {(row as unknown[]).map((cell, j) => (
                    <Table.Td key={j}>
                      {cell === null ? (
                        <Text c="dimmed" fs="italic" size="sm">
                          null
                        </Text>
                      ) : (
                        String(cell)
                      )}
                    </Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <TablePagination
            page={page}
            totalPages={totalPages}
            total={total}
            pageSize={pageSize}
            onChange={setPage}
          />
          {result.truncated && (
            <Text size="sm" c="dimmed" ta="center" pt="xs">
              Results truncated to {result.row_count} rows by server limit
            </Text>
          )}
        </Paper>
      )}

      {result.suggested_followups.length > 0 && (
        <Paper withBorder p="md">
          <Text fw={600} mb="xs">
            Suggested follow-up questions
          </Text>
          <Stack gap="xs">
            {result.suggested_followups.map((q, i) => (
              <Text key={i} size="sm" c="blue">
                {q}
              </Text>
            ))}
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
