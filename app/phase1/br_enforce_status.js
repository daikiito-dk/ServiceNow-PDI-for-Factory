/**
 * ステータス遷移の強制(roadmap 1-2)
 * テーブル: x_2221323_loan_p_0_request / タイミング: before update
 *
 * ルール:
 *  - ステータス変更は審査担当者(loan_underwriter)のみ可能
 *  - 許可される遷移:
 *      received    -> reviewing | rejected
 *      reviewing   -> conditional | approved | rejected
 *      conditional -> approved | rejected
 *    (approved / rejected は終点)
 */
(function executeRule(current, previous /*null when async*/) {

  // GlideElement のままだと == / indexOf が値ではなくオブジェクト比較になるため文字列化する
  var from = String(previous ? previous.status : current.status);
  var to = String(current.status);
  if (from == to) {
    return; // ステータス変更なし
  }

  if (!gs.hasRole('x_2221323_loan_p_0.loan_underwriter')) {
    gs.addErrorMessage('ステータスの変更は審査担当者のみ行えます。');
    current.setAbortAction(true);
    return;
  }

  var allowed = {
    received: ['reviewing', 'rejected'],
    reviewing: ['conditional', 'approved', 'rejected'],
    conditional: ['approved', 'rejected']
  };

  if (!allowed[from] || allowed[from].indexOf(to) < 0) {
    gs.addErrorMessage('ステータスを「' + from + '」から「' + to + '」へ変更することはできません。');
    current.setAbortAction(true);
  }

})(current, previous);
