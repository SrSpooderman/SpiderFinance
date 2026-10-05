import './RepositoryCredit.css'

export default function RepositoryCredit() {
  return <a
    className="repository-credit"
    href="https://github.com/SrSpooderman/SpiderFinance"
    target="_blank"
    rel="noopener noreferrer"
    aria-label="Repositorio de SpiderFinance en GitHub (se abre en una pestaña nueva)"
  >
    <span>Powered by</span>
    <strong>SrSpooderman/SpiderFinance <span aria-hidden="true">↗</span></strong>
  </a>
}
