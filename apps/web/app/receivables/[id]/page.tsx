import { ReceivableDetail } from "../../../components/receivable-detail";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ReceivableDetail key={id} id={id} />;
}
