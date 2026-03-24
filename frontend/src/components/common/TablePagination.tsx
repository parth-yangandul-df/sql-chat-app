import { Group, Pagination, Text } from '@mantine/core';

interface TablePaginationProps {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
}

export function TablePagination({
  page,
  totalPages,
  total,
  pageSize,
  onChange,
}: TablePaginationProps) {
  if (totalPages <= 1) return null;

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <Group justify="space-between" mt="sm">
      <Text size="sm" c="dimmed">
        Showing {from}–{to} of {total}
      </Text>
      <Pagination total={totalPages} value={page} onChange={onChange} size="sm" />
    </Group>
  );
}
