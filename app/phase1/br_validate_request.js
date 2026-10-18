/**
 * 融資事前審査 入力検証(roadmap 1-1)
 * テーブル: x_2221323_loan_p_0_request / タイミング: before insert & update
 *
 * 検証内容:
 *  - 融資希望金額は 0 < 金額 <= 上限プロパティ(x_2221323_loan_p_0.max_request_amount)
 *  - 年収は未入力可、入力する場合は 0 より大きい
 *  - 顧客名は空白以外必須
 *  - 新規作成時のステータスは「申請受付(received)」のみ。未指定は可(辞書の既定値 received が入る)
 *    (作成時は全フィールドを設定できるため、承認済みの申請を直接作れないようにする)
 */
(function executeRule(current, previous /*null when async*/) {

  var MAX = parseInt(gs.getProperty('x_2221323_loan_p_0.max_request_amount', '100000000'), 10);

  // GlideElement は空でもオブジェクトとして truthy になるため、必ず文字列化して判定する
  var amount = parseFloat(String(current.requested_amount) || 0);
  if (!(amount > 0)) {
    gs.addErrorMessage('融資希望金額は0より大きい金額を入力してください。');
    current.setAbortAction(true);
  } else if (amount > MAX) {
    gs.addErrorMessage('融資希望金額が上限(' + MAX + '円)を超えています。');
    current.setAbortAction(true);
  }

  if (!current.annual_income.nil() && !(parseFloat(String(current.annual_income)) > 0)) {
    gs.addErrorMessage('年収は0より大きい金額を入力してください。');
    current.setAbortAction(true);
  }

  if (!String(current.customer_name || '').trim()) {
    gs.addErrorMessage('顧客名は必須です。');
    current.setAbortAction(true);
  }

  if (current.operation() == 'insert' && !current.status.nil() && String(current.status) != 'received') {
    gs.addErrorMessage('新規の申請はステータス「申請受付」で登録してください。');
    current.setAbortAction(true);
  }

})(current, previous);
